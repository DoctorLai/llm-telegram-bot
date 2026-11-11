from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml
from telegram import Bot, Chat, Message, Update, User

import bot


@pytest.fixture
def config_data():
    return yaml.safe_load(bot.CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def config_path(tmp_path, monkeypatch, config_data):
    monkeypatch.setenv("YOUR_TELEGRAM_BOT_API_TOKEN", "123456:test-telegram-token")
    monkeypatch.setenv("YOUR_OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("YOUR_GROK_API_KEY", "test-grok-key")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    return path


@pytest.fixture
def settings(config_path):
    return bot.load_config(config_path)


@pytest.fixture
def telegram_update():
    telegram_bot = AsyncMock(spec=Bot)
    message = Message(
        message_id=7,
        date=datetime(2026, 1, 1, tzinfo=UTC),
        chat=Chat(id=123, type="private"),
        from_user=User(id=42, first_name="Test", is_bot=False, language_code="en"),
        text="/ask What is AI?",
    )
    message.set_bot(telegram_bot)
    update = Update(update_id=1, message=message)
    context = SimpleNamespace(args=["What", "is", "AI?"], error=None)
    return update, context, telegram_bot
