"""Shared fake OpenAI-style client for every model test.

Replies are consumed in order. A reply may be a string (returned as the message
content), a dict (sent as JSON) or an Exception (raised from create()).
"""

import json
from types import SimpleNamespace

from book.llm import Provider


class FakeChat:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError("FakeClient ran out of replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, dict):
            reply = json.dumps(reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


class FakeClient:
    def __init__(self, *replies):
        self.chat = SimpleNamespace(completions=FakeChat(replies))

    @property
    def calls(self):
        return self.chat.completions.calls


def fake_provider(name: str, *replies, model: str = "m", json_mode: bool = True) -> Provider:
    client = FakeClient(*replies)
    return Provider(name, model, lambda: client, json_mode)


def no_call_provider(name: str = "nope") -> Provider:
    def boom():
        raise AssertionError(f"provider {name} must not be used")

    return Provider(name, "m", boom)
