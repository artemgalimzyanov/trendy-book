import pytest

from book import llm
from tests.fakes import fake_provider


def test_providers_put_openai_first_and_gemini_second(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    order = llm.providers()
    assert [p.name for p in order] == ["openai", "gemini"]
    assert order[0].model == llm.OPENAI_WRITER_MODEL == "gpt-5.4-mini"


def test_providers_skip_a_provider_without_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert [p.name for p in llm.providers()] == ["openai"]
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    assert [p.name for p in llm.providers()] == ["gemini"]


def test_providers_without_any_key_fail_only_when_used(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    order = llm.providers()  # must not raise: dry runs need no key
    with pytest.raises(RuntimeError):
        order[0].client


def test_gemini_client_uses_the_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    client = llm.gemini_provider().client
    assert str(client.base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_clients_give_up_quickly_so_the_fallback_gets_a_turn(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    for provider in (llm.gemini_provider(), llm.openai_provider()):
        assert provider.client.timeout == 120 and provider.client.max_retries == 1


def test_chat_json_sends_json_mode_and_parses():
    provider = fake_provider("openai", '{"ok": true}', model="gpt-x")
    assert llm.chat_json(provider, "sys", "user") == {"ok": True}
    call = provider.client.calls[0]
    assert call["model"] == "gpt-x"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]


def test_chat_json_without_json_mode_strips_fences():
    provider = fake_provider("gemini", '```json\n{"ok": 1}\n```', json_mode=False)
    assert llm.chat_json(provider, "s", "u") == {"ok": 1}
    assert "response_format" not in provider.client.calls[0]


@pytest.mark.parametrize("reply", ["not json", "[1, 2]", "", "```\nnope\n```"])
def test_chat_json_raises_on_anything_but_a_json_object(reply):
    with pytest.raises(ValueError):
        llm.chat_json(fake_provider("x", reply), "s", "u")


def test_label_names_provider_and_model():
    assert fake_provider("gemini", model="flash").label == "gemini:flash"
