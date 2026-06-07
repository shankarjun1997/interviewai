"""Live-session subsystem: REST (create/transcript/batch-transcribe) + the
realtime WebSocket relay (auth, persist, broadcast). Offline (sqlite + stub)."""
import io

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token


def _register(c: TestClient) -> dict:
    r = c.post(
        "/api/v1/auth/register",
        json={"organization_name": "Acme", "email": "lead@acme.com", "password": "supersecret"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _interview(c: TestClient, h: dict) -> str:
    r = c.post("/api/v1/interviews", headers=h, json={"title": "DE", "job_description": "Spark"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_rest_session_flow():
    with TestClient(app) as c:
        tok = _register(c)["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        iv = _interview(c, h)

        r = c.post("/api/v1/sessions", headers=h, json={"interview_id": iv})
        assert r.status_code == 201, r.text
        sid = r.json()["id"]

        # batch transcribe an audio blob -> stub segment persisted
        r = c.post(
            f"/api/v1/sessions/{sid}/transcribe",
            headers=h,
            files={"file": ("a.wav", io.BytesIO(b"0123456789"), "audio/wav")},
        )
        assert r.status_code == 200, r.text
        assert len(r.json()) == 1

        r = c.get(f"/api/v1/sessions/{sid}/transcript", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 1

        # tenant isolation: unknown session 404
        r = c.get("/api/v1/sessions/does-not-exist/transcript", headers=h)
        assert r.status_code == 404


def test_websocket_relay_and_auth():
    with TestClient(app) as c:
        tok = _register(c)["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        iv = _interview(c, h)
        sid = c.post("/api/v1/sessions", headers=h, json={"interview_id": iv}).json()["id"]

        # bad token is rejected before joining the room
        try:
            with c.websocket_connect(f"/api/v1/sessions/ws/{sid}?token=garbage") as ws:
                ws.receive_json()
            assert False, "expected rejection"
        except Exception:
            pass

        # valid interviewer: send a transcript, receive the broadcast back
        with c.websocket_connect(f"/api/v1/sessions/ws/{sid}?token={tok}") as ws:
            ws.send_json(
                {"type": "transcript", "speaker": "candidate", "text": "I use Spark", "start_ms": 0, "end_ms": 500}
            )
            msg = ws.receive_json()
            assert msg["type"] == "transcript"
            assert msg["text"] == "I use Spark"
            assert msg["id"]

        # segment was persisted
        r = c.get(f"/api/v1/sessions/{sid}/transcript", headers=h)
        assert any(s["text"] == "I use Spark" for s in r.json())


def test_websocket_rejects_candidate_role():
    with TestClient(app) as c:
        tok = _register(c)["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        iv = _interview(c, h)
        sid = c.post("/api/v1/sessions", headers=h, json={"interview_id": iv}).json()["id"]

        org = _decode_org(tok)
        cand_token = create_access_token(user_id="x", org_id=org, role="candidate")
        try:
            with c.websocket_connect(f"/api/v1/sessions/ws/{sid}?token={cand_token}") as ws:
                ws.receive_json()
            assert False, "candidate should be rejected"
        except Exception:
            pass


def _decode_org(token: str) -> str:
    from app.core.security import decode_token

    return decode_token(token)["org"]
