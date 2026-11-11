import json
from dataclasses import replace

import httpx
import pytest

import bot


@pytest.fixture
def transport(monkeypatch):
    client_type = httpx.AsyncClient

    def install(handler):
        mock_transport = httpx.MockTransport(handler)
        monkeypatch.setattr(
            bot.httpx,
            "AsyncClient",
            lambda **kwargs: client_type(transport=mock_transport, **kwargs),
        )

    return install


@pytest.mark.parametrize("name", ["grok", "openai"])
async def test_chat_completion_request(name, settings, transport):
    provider = settings.providers[name]
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "An answer."}}]})

    transport(respond)
    assert await bot.get_response(provider, "A question?", 17) == "An answer."
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == provider.api_url
    assert request.headers["Authorization"] == f"Bearer {provider.api_key}"
    assert request.extensions["timeout"]["read"] == 17
    assert json.loads(request.content) == {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": provider.role},
            {"role": "user", "content": "A question?"},
        ],
        "stream": False,
        "temperature": provider.temperature,
        "max_tokens": provider.max_tokens,
    }


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_http_errors_do_not_expose_secrets(status, settings, transport, caplog):
    transport(lambda request: httpx.Response(status, text="private provider details"))
    with pytest.raises(bot.ProviderError, match="request failed"):
        await bot.get_response(settings.providers["grok"], "private prompt", 30)
    assert "HTTPStatusError" in caplog.text
    for private in ["private provider details", "private prompt", "test-grok-key"]:
        assert private not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": None},
        {"choices": [{}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "   "}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"content": ["not text"]}}]},
    ],
)
async def test_malformed_provider_data(payload, settings, transport):
    transport(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(bot.ProviderError):
        await bot.get_response(settings.providers["grok"], "question", 30)


async def test_non_json_provider_data(settings, transport):
    transport(lambda request: httpx.Response(200, text="not JSON"))
    with pytest.raises(bot.ProviderError):
        await bot.get_response(settings.providers["grok"], "question", 30)


async def test_request_timeout(settings, transport, caplog):
    def respond(request):
        raise httpx.ReadTimeout("sensitive URL and token", request=request)

    transport(respond)
    with pytest.raises(bot.ProviderError):
        await bot.get_response(settings.providers["grok"], "question", 0.1)
    assert "ReadTimeout" in caplog.text
    assert "sensitive URL and token" not in caplog.text


async def test_disabled_provider_fails_without_network(settings, transport, caplog):
    def unexpected_request(request):
        pytest.fail("A disabled provider must not receive an HTTP request")

    transport(unexpected_request)
    with pytest.raises(bot.ProviderError, match="not configured"):
        await bot.get_response(replace(settings.providers["openai"], api_key=""), "question", 30)
    assert "no API key" in caplog.text
