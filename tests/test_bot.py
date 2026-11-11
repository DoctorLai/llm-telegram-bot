import asyncio
import os
import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Update
from telegram.constants import ChatAction
from telegram.error import Forbidden, TimedOut

import bot
from localization import translate


@pytest.mark.parametrize(
    "text",
    ["", "a", "a" * 4095, "a" * 4096, "a" * 4097, "a" * 8200, "😀" * 4096, "a" * 4095 + "😀b"],
)
def test_message_splitting_preserves_unicode_and_telegram_limit(text):
    chunks = bot.split_message(text)
    assert "".join(chunks) == text
    assert all(0 < len(chunk.encode("utf-16-le")) // 2 <= 4096 for chunk in chunks)


@pytest.mark.parametrize(
    ("args", "provider", "prompt"),
    [
        (["What", "is", "AI?"], "grok", "What is AI?"),
        (["openai", "Hello"], "openai", "Hello"),
        (["OpenAI", "Hello"], "openai", "Hello"),
        (["unknown", "question"], "grok", "unknown question"),
    ],
)
async def test_ask_routes_prompts(args, provider, prompt, settings, telegram_update, monkeypatch):
    update, context, telegram_bot = telegram_update
    context.args = args
    request = AsyncMock(return_value="Answer")
    monkeypatch.setattr(bot, "get_response", request)
    assistant = bot.TelegramAssistant(settings)
    await assistant.ask(update, context)
    request.assert_awaited_once_with(settings.providers[provider], prompt, settings.request_timeout)
    telegram_bot.send_chat_action.assert_awaited_once_with(chat_id=123, action=ChatAction.TYPING)
    assert telegram_bot.send_message.await_args.kwargs["text"] == "Answer"
    assert telegram_bot.send_message.await_args.kwargs["reply_parameters"].message_id == 7
    assert not hasattr(assistant, "user_memory")


async def test_typing_indicator_failure_does_not_abort_question(
    settings, telegram_update, monkeypatch, caplog
):
    update, context, telegram_bot = telegram_update
    telegram_bot.send_chat_action.side_effect = TimedOut("private request details")
    request = AsyncMock(return_value="Answer")
    monkeypatch.setattr(bot, "get_response", request)
    await bot.TelegramAssistant(settings).ask(update, context)
    request.assert_awaited_once()
    assert telegram_bot.send_message.await_args.kwargs["text"] == "Answer"
    assert "TimedOut" in caplog.text
    assert "private request details" not in caplog.text


@pytest.mark.parametrize("args", [None, [], ["openai"], [" "], ["grok", " "]])
async def test_empty_prompts_do_not_consume_rate_limit(
    args, settings, telegram_update, monkeypatch
):
    update, context, telegram_bot = telegram_update
    context.args = args
    request = AsyncMock()
    monkeypatch.setattr(bot, "get_response", request)
    assistant = bot.TelegramAssistant(settings)
    await assistant.ask(update, context)
    assert telegram_bot.send_message.await_args.kwargs["text"] == translate("en", "empty_prompt")
    request.assert_not_awaited()
    assert assistant.last_query_time == {}


async def test_rate_limit_boundary_and_expired_state(settings, telegram_update, monkeypatch):
    update, context, telegram_bot = telegram_update
    clock = Mock(side_effect=[100, 109.99, 110])
    monkeypatch.setattr(bot, "time", SimpleNamespace(monotonic=clock))
    request = AsyncMock(return_value="Answer")
    monkeypatch.setattr(bot, "get_response", request)
    assistant = bot.TelegramAssistant(settings)
    assistant.last_query_time[1234] = 80
    await assistant.ask(update, context)
    assert assistant.last_query_time == {42: 100}
    await assistant.ask(update, context)
    assert request.await_count == 1
    assert telegram_bot.send_message.await_args.kwargs["text"] == translate(
        "en", "rate_limit", seconds=10
    )
    await assistant.ask(update, context)
    assert request.await_count == 2
    assert assistant.last_query_time == {42: 110}


async def test_zero_rate_limit(settings, telegram_update, monkeypatch):
    update, context, _ = telegram_update
    request = AsyncMock(return_value="Answer")
    monkeypatch.setattr(bot, "get_response", request)
    assistant = bot.TelegramAssistant(replace(settings, rate_limit=0))
    await assistant.ask(update, context)
    await assistant.ask(update, context)
    assert request.await_count == 2


async def test_ask_handles_failure_and_preserves_cooldown(settings, telegram_update, monkeypatch):
    update, context, telegram_bot = telegram_update
    monkeypatch.setattr(
        bot, "get_response", AsyncMock(side_effect=bot.ProviderError("private data"))
    )
    assistant = bot.TelegramAssistant(settings)
    await assistant.ask(update, context)
    assert telegram_bot.send_message.await_args.kwargs["text"] == translate("en", "provider_error")
    assert 42 in assistant.last_query_time


async def test_long_response_is_sent_in_order(settings, telegram_update, monkeypatch):
    update, context, telegram_bot = telegram_update
    response = "a" * 4095 + "😀" * 4096
    monkeypatch.setattr(bot, "get_response", AsyncMock(return_value=response))
    await bot.TelegramAssistant(settings).ask(update, context)
    messages = [call.kwargs["text"] for call in telegram_bot.send_message.await_args_list]
    assert messages == bot.split_message(response)


@pytest.mark.parametrize("command", ["start", "help", "ping", "version", "ask", "providers"])
async def test_updates_without_messages(settings, command):
    await getattr(bot.TelegramAssistant(settings), command)(Update(1), SimpleNamespace(args=[]))


async def test_ask_without_a_user(settings, telegram_update):
    update, context, telegram_bot = telegram_update
    with update.message._unfrozen():
        update.message.from_user = None
    await bot.TelegramAssistant(settings).ask(update, context)
    telegram_bot.send_message.assert_not_awaited()


async def test_commands_and_latency(settings, telegram_update, monkeypatch):
    update, context, telegram_bot = telegram_update
    assistant = bot.TelegramAssistant(settings)
    await assistant.start(update, context)
    texts = [call.kwargs["text"] for call in telegram_bot.send_message.await_args_list]
    assert texts == [translate("en", "welcome", seconds=10), translate("en", "help")]
    await assistant.version(update, context)
    assert telegram_bot.send_message.await_args.kwargs["text"] == f"Version: {bot.VERSION}"
    monkeypatch.setattr(bot, "time", SimpleNamespace(monotonic=Mock(side_effect=[1.0, 1.125])))
    await assistant.ping(update, context)
    assert telegram_bot.send_message.await_args.kwargs["text"] == "Reply latency: 125.00 ms."


async def test_localized_command(settings, telegram_update):
    update, context, telegram_bot = telegram_update
    with update.effective_user._unfrozen():
        update.effective_user.language_code = "zh-Hant-HK"
    await bot.TelegramAssistant(settings).help(update, context)
    assert telegram_bot.send_message.await_args.kwargs["text"] == translate("zh-TW", "help")


async def test_providers_lists_models_without_secrets_or_using_cooldown(settings, telegram_update):
    update, context, telegram_bot = telegram_update
    settings = replace(
        settings,
        providers={
            **settings.providers,
            "openai": replace(settings.providers["openai"], api_key=""),
        },
    )
    assistant = bot.TelegramAssistant(settings)
    assistant.last_query_time[42] = 100
    await assistant.providers(update, context)
    reply = telegram_bot.send_message.await_args.kwargs["text"]
    assert reply == translate(
        "en", "providers", default="grok", providers=f"grok: {settings.providers['grok'].model}"
    )
    assert "openai" not in reply
    assert "test-grok-key" not in reply
    assert "https://" not in reply
    assert assistant.last_query_time == {42: 100}


async def test_provider_listing_localization_and_long_messages(settings, telegram_update):
    update, context, telegram_bot = telegram_update
    with update.effective_user._unfrozen():
        update.effective_user.language_code = "zh-Hant"
    providers = {
        f"provider-{index}": replace(settings.providers["grok"], model="large-model-" * 20)
        for index in range(40)
    }
    settings = replace(settings, providers=providers, default_model="provider-0")
    await bot.TelegramAssistant(settings).providers(update, context)
    chunks = [call.kwargs["text"] for call in telegram_bot.send_message.await_args_list]
    expected = translate(
        "zh-TW",
        "providers",
        default=settings.default_model,
        providers="\n".join(f"{name}: {provider.model}" for name, provider in providers.items()),
    )
    assert chunks == bot.split_message(expected)
    assert len(chunks) > 1


async def test_provider_wait_does_not_block_ping_or_allow_duplicate_requests(
    settings, telegram_update, monkeypatch
):
    update, context, telegram_bot = telegram_update
    entered, finish = asyncio.Event(), asyncio.Event()

    async def response(*args):
        entered.set()
        await finish.wait()
        return "Completed answer"

    request = AsyncMock(side_effect=response)
    monkeypatch.setattr(bot, "get_response", request)
    assistant = bot.TelegramAssistant(settings)
    async with asyncio.TaskGroup() as group:
        group.create_task(assistant.ask(update, context))
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            await asyncio.wait_for(assistant.ping(update, context), timeout=1)
            await asyncio.wait_for(assistant.ask(update, context), timeout=1)
            assert request.await_count == 1
            texts = [call.kwargs["text"] for call in telegram_bot.send_message.await_args_list]
            assert translate("en", "pong") in texts
            assert translate("en", "rate_limit", seconds=10) in texts
        finally:
            finish.set()
    assert telegram_bot.send_message.await_args.kwargs["text"] == "Completed answer"


async def test_unhandled_error_is_logged_without_sensitive_details(telegram_update, caplog):
    update, context, telegram_bot = telegram_update
    context.error = RuntimeError("secret-token and private question")
    await bot.on_error(update, context)
    assert "RuntimeError" in caplog.text
    assert "secret-token" not in caplog.text
    assert "private question" not in caplog.text
    assert telegram_bot.send_message.await_args.kwargs["text"] == translate("en", "provider_error")
    await bot.on_error(None, context)
    await bot.on_error(Update(2), context)


async def test_error_notification_failure_does_not_leak_details(telegram_update, caplog):
    update, context, telegram_bot = telegram_update
    context.error = RuntimeError("private prompt")
    telegram_bot.send_message.side_effect = Forbidden("private Telegram error")
    await bot.on_error(update, context)
    assert "Forbidden" in caplog.text
    assert "private Telegram error" not in caplog.text
    assert "private prompt" not in caplog.text


def test_application_registers_only_implemented_commands(settings):
    application = bot.build_application(settings)
    assert {name for handler in application.handlers[0] for name in handler.commands} == {
        "start",
        "help",
        "ping",
        "ask",
        "providers",
        "version",
    }
    assert bot.on_error in application.error_handlers


def test_main_starts_polling_with_valid_config(config_path, monkeypatch):
    application = Mock()
    builder = Mock(return_value=application)
    monkeypatch.setattr(bot, "build_application", builder)
    monkeypatch.setattr(sys, "argv", ["bot.py", "--config", str(config_path)])
    bot.main()
    assert builder.call_args.args[0].default_model == "grok"
    application.run_polling.assert_called_once_with(allowed_updates=["message"])


def test_offline_config_check_never_builds_or_polls(config_path, monkeypatch, capsys):
    builder = Mock(side_effect=AssertionError("Config checks must not create network clients"))
    monkeypatch.setattr(bot, "build_application", builder)
    monkeypatch.setattr(sys, "argv", ["bot.py", "--config", str(config_path), "--check-config"])
    bot.main()
    builder.assert_not_called()
    output = capsys.readouterr().out
    assert "Configuration is valid." in output
    assert "not checked online" in output
    assert "test-grok-key" not in output
    assert "test-telegram-token" not in output


def test_offline_config_check_fails_without_default_credentials(config_path, monkeypatch, capsys):
    monkeypatch.delenv("YOUR_GROK_API_KEY")
    monkeypatch.setattr(sys, "argv", ["bot.py", "--config", str(config_path), "--check-config"])
    with pytest.raises(SystemExit) as error:
        bot.main()
    assert error.value.code == 1
    assert capsys.readouterr().out == ""


def test_main_loads_dotenv_next_to_config(config_path, monkeypatch):
    monkeypatch.delenv("YOUR_GROK_API_KEY")
    config_path.with_name(".env").write_text(
        "YOUR_GROK_API_KEY=dotenv-test-key\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", ["bot.py", "--config", str(config_path)])
    builder = Mock()
    monkeypatch.setattr(bot, "build_application", builder)
    bot.main()
    assert builder.call_args.args[0].providers["grok"].api_key == "dotenv-test-key"
    monkeypatch.delenv("YOUR_GROK_API_KEY")


@pytest.mark.parametrize("contents", [None, "telegram: [private-token", "{}"])
def test_main_invalid_config_exits_without_leaking_values(tmp_path, monkeypatch, caplog, contents):
    path = tmp_path / "config.yaml"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bot.py", "--config", str(path)])
    with pytest.raises(SystemExit) as error:
        bot.main()
    assert error.value.code == 1
    assert "Cannot load configuration" in caplog.text
    assert "private-token" not in caplog.text


def test_cli_version_requires_no_credentials(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bot.py", "--version"])
    with pytest.raises(SystemExit) as error:
        bot.main()
    assert error.value.code == 0
    assert capsys.readouterr().out.strip() == bot.VERSION


def test_real_polling_lifecycle_without_external_services(config_path):
    program = """
import asyncio
import sys
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx
import bot

state = {"delivered": False, "replies": [], "application": None}
real_client = httpx.AsyncClient
real_builder = bot.build_application
user = {"id": 123456, "first_name": "Test", "is_bot": True, "username": "fixture_bot"}

def respond(request):
    method = request.url.path.rsplit("/", 1)[-1]
    if method == "getMe":
        result = user
    elif method == "deleteWebhook":
        result = True
    elif method == "getUpdates":
        result = [] if state["delivered"] else [{
            "update_id": 1,
            "message": {
                "message_id": 7, "date": 1,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 42, "first_name": "Test", "is_bot": False},
                "text": "/version",
                "entities": [{"type": "bot_command", "offset": 0, "length": 8}],
            },
        }]
        state["delivered"] = True
    elif method == "sendMessage":
        form = parse_qs(request.content.decode())
        state["replies"].append(form["text"][0])
        result = {
            "message_id": 8, "date": 1,
            "chat": {"id": 123, "type": "private"}, "text": form["text"][0],
        }
        asyncio.get_running_loop().call_later(0.01, state["application"].stop_running)
    else:
        raise AssertionError(f"Unexpected API method: {method}")
    return httpx.Response(200, json={"ok": True, "result": result})

async def watchdog(application):
    asyncio.get_running_loop().call_later(1, application.stop_running)

def build(settings):
    application = real_builder(settings)
    state["application"] = application
    application.post_init = watchdog
    return application

def client(**kwargs):
    kwargs["transport"] = httpx.MockTransport(respond)
    return real_client(**kwargs)

with patch.object(httpx, "AsyncClient", client), patch.object(bot, "build_application", build):
    sys.argv = ["bot.py", "--config", sys.argv[1]]
    bot.main()
assert state["replies"] == [f"Version: {bot.VERSION}"], state["replies"]
assert not state["application"].running
print("Polling, command dispatch, reply, and shutdown passed.")
"""
    environment = {**os.environ, "PYTHONPATH": str(bot.CONFIG_PATH.parent)}
    result = subprocess.run(
        [sys.executable, "-c", program, str(config_path)],
        cwd=config_path.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "Polling, command dispatch, reply, and shutdown passed." in result.stdout
