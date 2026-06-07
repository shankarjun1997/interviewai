"""Provider-abstracted transcription. Live session relay depends on this.

Two paths:
- Realtime: the WebSocket relays client-produced transcript segments (browser
  STT or a Deepgram live socket on the client) — server persists + broadcasts.
- Batch: `transcribe()` turns an uploaded audio blob into speaker-labeled
  segments via the configured provider (Deepgram default).

Falls back to a deterministic stub when no API key is set, so the live session
runs end-to-end offline.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass
class Segment:
    speaker: str
    text: str
    start_ms: int
    end_ms: int


class Transcriber:
    async def transcribe(self, audio: bytes, *, content_type: str = "audio/wav") -> list[Segment]:
        raise NotImplementedError


class DeepgramTranscriber(Transcriber):
    def __init__(self) -> None:
        from deepgram import DeepgramClient

        self._client = DeepgramClient(settings.deepgram_api_key)

    async def transcribe(self, audio: bytes, *, content_type: str = "audio/wav") -> list[Segment]:
        from deepgram import PrerecordedOptions

        opts = PrerecordedOptions(model="nova-2", diarize=True, smart_format=True, utterances=True)
        resp = await self._client.listen.asyncrest.v("1").transcribe_file(
            {"buffer": audio, "mimetype": content_type}, opts
        )
        segments: list[Segment] = []
        utterances = getattr(resp.results, "utterances", None) or []
        for u in utterances:
            spk = getattr(u, "speaker", 0)
            segments.append(
                Segment(
                    speaker=f"speaker_{spk}",
                    text=u.transcript,
                    start_ms=int(u.start * 1000),
                    end_ms=int(u.end * 1000),
                )
            )
        return segments


class StubTranscriber(Transcriber):
    """Deterministic offline transcriber: one segment derived from blob size."""

    async def transcribe(self, audio: bytes, *, content_type: str = "audio/wav") -> list[Segment]:
        return [
            Segment(
                speaker="candidate",
                text=f"[stub transcription of {len(audio)} bytes — set DEEPGRAM_API_KEY for real audio]",
                start_ms=0,
                end_ms=max(1000, len(audio)),
            )
        ]


def get_transcriber() -> Transcriber:
    if settings.transcription_provider == "deepgram" and settings.deepgram_api_key:
        return DeepgramTranscriber()
    return StubTranscriber()
