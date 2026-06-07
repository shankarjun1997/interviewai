"""Provider-abstracted LLM client. All AI subsystems depend on this contract.

Swap providers via settings.llm_provider without touching callers. Returns plain
strings (or parsed JSON via complete_json). Falls back to a deterministic stub
when no API key is configured so the platform runs end-to-end in dev/tests.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings

settings = get_settings()


class LLMClient:
    async def complete(self, *, system: str, prompt: str, max_tokens: int = 1024) -> str:
        raise NotImplementedError

    async def complete_json(self, *, system: str, prompt: str, max_tokens: int = 2048) -> Any:
        raw = await self.complete(
            system=system + "\nRespond with valid JSON only, no prose.",
            prompt=prompt,
            max_tokens=max_tokens,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)


class AnthropicClient(LLMClient):
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def complete(self, *, system: str, prompt: str, max_tokens: int = 1024) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")


class StubClient(LLMClient):
    """Deterministic offline stub so the full flow works without API keys."""

    async def complete(self, *, system: str, prompt: str, max_tokens: int = 1024) -> str:
        return json.dumps(
            {
                "stub": True,
                "note": "Configure ANTHROPIC_API_KEY for real generations.",
                "echo_prompt": prompt[:200],
            }
        )


def get_llm() -> LLMClient:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicClient()
    return StubClient()
