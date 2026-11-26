import pytest

from book import llm
from tests.fakes import fake_provider


def test_providers_put_gemini_first_when_key_is_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    names = [p.name for p in llm.providers()]
    assert names == ["gemini", "openai"]


def test_providers_skip_gemini_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    order = llm.providers()
    assert [p.name for p in order] == ["openai"]
    assert order[0].model == llm.OPENAI_WRITER_MODEL == "gpt-5.4-mini"


def test_providers_create_no_client_until_used(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm.providers()  # must not raise on the missing OpenAI key


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
