"""Model providers for the writer: Gemini (free tier) first, OpenAI as the fallback.

Both are reached with the `openai` package: Gemini through its OpenAI-compatible endpoint.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable

from book.config import gemini_client, has_env, openai_client

log = logging.getLogger(__name__)

# Provisional until `main.py llm-check` lists the models on a real key; GEMINI_MODEL in
# the environment overrides it without a code change.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"
GEMINI_JSON_MODE = True  # turn off if Gemini rejects response_format; fences are stripped anyway
OPENAI_WRITER_MODEL = "gpt-5.4-mini"

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass
class Provider:
    """One model behind one client; the client is created on first use."""

    name: str
    model: str
    make_client: Callable
    json_mode: bool = True
    _client: object = field(default=None, repr=False)

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    @property
    def client(self):
        if self._client is None:
            self._client = self.make_client()
        return self._client


def gemini_provider() -> Provider:
    return Provider("gemini", GEMINI_MODEL, gemini_client, GEMINI_JSON_MODE)


def openai_provider() -> Provider:
    return Provider("openai", OPENAI_WRITER_MODEL, openai_client, True)


def providers() -> list[Provider]:
    """Provider order for the writer. Gemini is skipped when GEMINI_API_KEY is missing."""
    order = []
    if has_env("GEMINI_API_KEY"):
        order.append(gemini_provider())
    else:
        log.info("GEMINI_API_KEY not set; writing with OpenAI only")
    order.append(openai_provider())
    return order


def strip_fences(text: str) -> str:
    match = _FENCE.match(text or "")
    return match.group(1) if match else (text or "").strip()


def parse_json_object(text: str) -> dict:
    """Parse a model reply into a dict, tolerating ``` fences; raise ValueError otherwise."""
    cleaned = strip_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Reply is not JSON ({exc}): {cleaned[:200]!r}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Reply is JSON but not an object: {cleaned[:200]!r}")
    return data


def chat_json(provider: Provider, system: str, user: str, followup: list[dict] | None = None) -> dict:
    """One chat call that must come back as a JSON object.

    followup: extra messages after the user message, e.g. the previous reply and a fix request.
    """
    kwargs = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            *(followup or []),
        ],
    }
    if provider.json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = provider.client.chat.completions.create(**kwargs)
    return parse_json_object(response.choices[0].message.content or "")
