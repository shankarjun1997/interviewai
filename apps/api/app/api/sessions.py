from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.security import decode_token
from app.db.base import SessionLocal, get_db
from app.models import Interview, Session, TranscriptSegment, UserRole
from app.services.realtime import manager
from app.services.transcription import get_transcriber

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
InterviewerDep = require_role(UserRole.interviewer, UserRole.super_admin)

_ALLOWED_SPEAKERS_PREFIX = ("candidate", "interviewer", "speaker_")


class SessionCreate(BaseModel):
    interview_id: str
    round_id: str | None = None


class SessionOut(BaseModel):
    id: str
    interview_id: str
    status: str

    class Config:
        from_attributes = True


class SegmentOut(BaseModel):
    id: str
    speaker: str
    text: str
    start_ms: int
    end_ms: int

    class Config:
        from_attributes = True


async def _session_in_org(session_id: str, org_id: str, db: AsyncSession) -> Session:
    sess = await db.scalar(
        select(Session)
        .join(Interview, Interview.id == Session.interview_id)
        .where(Session.id == session_id, Interview.organization_id == org_id)
    )
    if not sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return sess


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    iv = await db.scalar(
        select(Interview).where(
            Interview.id == body.interview_id,
            Interview.organization_id == user.organization_id,  # tenant isolation
        )
    )
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    sess = Session(interview_id=iv.id, round_id=body.round_id, status="live")
    db.add(sess)
    await db.commit()
    return sess


@router.get("/{session_id}/transcript", response_model=list[SegmentOut])
async def get_transcript(
    session_id: str,
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    await _session_in_org(session_id, user.organization_id, db)
    rows = await db.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.session_id == session_id)
        .order_by(TranscriptSegment.start_ms)
    )
    return list(rows)


@router.post("/{session_id}/transcribe", response_model=list[SegmentOut])
async def transcribe_audio(
    session_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(InterviewerDep),
    db: AsyncSession = Depends(get_db),
):
    """Batch path: upload an audio blob, persist provider-produced segments."""
    await _session_in_org(session_id, user.organization_id, db)
    audio = await file.read()
    segments = await get_transcriber().transcribe(
        audio, content_type=file.content_type or "audio/wav"
    )
    created: list[TranscriptSegment] = []
    for seg in segments:
        row = TranscriptSegment(
            session_id=session_id,
            speaker=seg.speaker,
            text=seg.text,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
        )
        db.add(row)
        created.append(row)
    await db.commit()
    return created


@router.websocket("/ws/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str, token: str = ""):
    """Realtime relay. Auth via ?token= (WS can't carry bearer headers cleanly).

    Inbound message: {"type":"transcript","speaker","text","start_ms","end_ms"}
    Persisted then broadcast to everyone in the room as {"type":"transcript", ...}.
    """
    payload = decode_token(token)
    if not payload or payload.get("role") not in {
        UserRole.interviewer.value,
        UserRole.super_admin.value,
    }:
        await websocket.close(code=4401)
        return

    # tenant check before joining the room
    async with SessionLocal() as db:
        sess = await db.scalar(
            select(Session)
            .join(Interview, Interview.id == Session.interview_id)
            .where(Session.id == session_id, Interview.organization_id == payload["org"])
        )
        if not sess:
            await websocket.close(code=4404)
            return

    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "transcript":
                continue
            speaker = str(data.get("speaker", "candidate"))
            if not speaker.startswith(_ALLOWED_SPEAKERS_PREFIX):
                speaker = "candidate"
            seg = TranscriptSegment(
                session_id=session_id,
                speaker=speaker,
                text=str(data.get("text", "")),
                start_ms=int(data.get("start_ms", 0)),
                end_ms=int(data.get("end_ms", 0)),
            )
            async with SessionLocal() as db:
                db.add(seg)
                await db.commit()
                await db.refresh(seg)
            await manager.broadcast(
                session_id,
                {
                    "type": "transcript",
                    "id": seg.id,
                    "speaker": seg.speaker,
                    "text": seg.text,
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                },
            )
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception:
        manager.disconnect(session_id, websocket)
        await websocket.close(code=1011)
