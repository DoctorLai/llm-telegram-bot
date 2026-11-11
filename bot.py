"""Stateless Telegram commands backed by OpenAI-compatible chat endpoints."""

import argparse
import logging
import math
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml
from dotenv import load_dotenv
from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, ExtBot, JobQueue

from localization import translate

VERSION = "2026-11-11"
CONFIG_PATH = Path(__file__).with_name("config.yaml")
MESSAGE_LIMIT = 4096
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    api_url: str
    api_key: str
    model: str
    role: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class Settings:
    token: str
    default_model: str
    providers: dict[str, Provider]
    rate_limit: float
    request_timeout: float


class ProviderError(Exception):
    """A provider is unavailable or returned an unusable completion."""


def expand_env_vars(value: object) -> object:
    """Expand once; unset whole-value environment references become missing values."""
    if isinstance(value, dict):
        return {key: expand_env_vars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    if isinstance(value, str):
        variable = re.fullmatch(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))", value.strip())
        if variable and (variable[1] or variable[2]) not in os.environ:
            return None
        return os.path.expandvars(value)
    return value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be a mapping with string keys.")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be set; check config.yaml and environment variables.")
    return value.strip()


def _number(value: object, name: str, minimum: float, maximum: float = math.inf) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{name} must be a finite number between {minimum} and {maximum}.")
    return float(value)


def load_config(path: Path = CONFIG_PATH) -> Settings:
    """Read and validate YAML; require credentials only for the default provider."""
    with path.open(encoding="utf-8") as file:
        config = _mapping(expand_env_vars(yaml.safe_load(file)), "config")
    telegram = _mapping(config.get("telegram"), "telegram")
    llms = _mapping(config.get("llms"), "llms")
    default = _text(llms.get("default_model"), "llms.default_model")
    providers = {}
    for name, value in _mapping(llms.get("providers"), "llms.providers").items():
        if not name or name != name.lower() or any(char.isspace() for char in name):
            raise ValueError("Provider names must be nonempty lowercase words.")
        provider = _mapping(value, f"providers.{name}")
        url = _text(provider.get("api_url"), f"{name}.api_url")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"{name}.api_url must be an HTTP(S) URL.")
        key_value = provider.get("api_key")
        if key_value is not None and not isinstance(key_value, str):
            raise ValueError(f"{name}.api_key must be a string.")
        key = (key_value or "").strip()
        if name == default or key:
            key = _text(key, f"{name}.api_key")
        max_tokens = provider.get("max_tokens")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(f"{name}.max_tokens must be a positive integer.")
        providers[name] = Provider(
            api_url=url,
            api_key=key,
            model=_text(provider.get("model"), f"{name}.model"),
            role=_text(provider.get("role"), f"{name}.role"),
            temperature=_number(provider.get("temperature"), f"{name}.temperature", 0, 2),
            max_tokens=max_tokens,
        )
    if default not in providers:
        raise ValueError("llms.default_model must name a configured provider.")
    return Settings(
        token=_text(telegram.get("token"), "telegram.token"),
        default_model=default,
        providers=providers,
        rate_limit=_number(config.get("rate_limit"), "rate_limit", 0),
        request_timeout=_number(config.get("request_timeout", 30), "request_timeout", 0.1),
    )


async def get_response(provider: Provider, prompt: str, timeout: float) -> str:
    """Request a text completion without blocking Telegram's event loop."""
    if not provider.api_key:
        logger.warning("Requested provider has no API key configured.")
        raise ProviderError("Provider is not configured.")
    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": provider.role},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "temperature": provider.temperature,
        "max_tokens": provider.max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                provider.api_url,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Completion has no text.")
            return content
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
        # Exception messages can contain credentials, URLs, or provider response bodies.
        logger.warning("Provider request failed (%s).", type(error).__name__)
        raise ProviderError("Provider request failed.") from error


def split_message(text: str) -> list[str]:
    """Split text at Telegram's UTF-16 limit without breaking Unicode characters."""
    chunks = []
    start = units = 0
    for index, character in enumerate(text):
        size = 2 if ord(character) > 0xFFFF else 1
        if units + size > MESSAGE_LIMIT:
            chunks.append(text[start:index])
            start, units = index, 0
        units += size
    if start < len(text):
        chunks.append(text[start:])
    return chunks


class TelegramAssistant:
    """Command handlers with short-lived rate-limit state, not chat history."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_query_time: dict[int, float] = {}

    async def _reply(self, update: Update, key: str, **values: object) -> None:
        message = update.effective_message
        if message is None:
            logger.debug("Ignoring update without a message.")
            return
        language = update.effective_user.language_code if update.effective_user else None
        for chunk in split_message(translate(language, key, **values)):
            await message.reply_text(chunk, reply_to_message_id=message.message_id)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, "welcome", seconds=f"{self.settings.rate_limit:g}")
        await self.help(update, context)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, "help")

    async def ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        started = time.monotonic()
        await self._reply(update, "pong")
        await self._reply(
            update, "latency", milliseconds=f"{(time.monotonic() - started) * 1000:.2f}"
        )

    async def version(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, "version", version=VERSION)

    async def providers(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        available = "\n".join(
            f"{name}: {provider.model}"
            for name, provider in self.settings.providers.items()
            if provider.api_key
        )
        await self._reply(
            update, "providers", default=self.settings.default_model, providers=available
        )

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        if not isinstance(message, Message) or user is None:
            logger.debug("Ignoring ask without a message or user.")
            return
        args = context.args or []
        model = args[0].lower() if args else ""
        if model in self.settings.providers:
            prompt = " ".join(args[1:]).strip()
        else:
            model = self.settings.default_model
            prompt = " ".join(args).strip()
        if not prompt:
            await self._reply(update, "empty_prompt")
            return
        now = time.monotonic()
        self.last_query_time = {
            user_id: timestamp
            for user_id, timestamp in self.last_query_time.items()
            if now - timestamp < self.settings.rate_limit
        }
        if user.id in self.last_query_time:
            await self._reply(update, "rate_limit", seconds=f"{self.settings.rate_limit:g}")
            return
        self.last_query_time[user.id] = now
        try:
            await message.get_bot().send_chat_action(
                chat_id=message.chat_id, action=ChatAction.TYPING
            )
        except TelegramError as error:
            logger.warning("Cannot send typing indicator (%s).", type(error).__name__)
        try:
            response = await get_response(
                self.settings.providers[model], prompt, self.settings.request_timeout
            )
        except ProviderError:
            await self._reply(update, "provider_error")
            return
        for chunk in split_message(response):
            await message.reply_text(chunk, reply_to_message_id=message.message_id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the failure category without leaking prompts, tokens, or HTTP bodies."""
    logger.error("Unhandled bot error (%s).", type(context.error).__name__)
    if isinstance(update, Update) and update.effective_message is not None:
        language = update.effective_user.language_code if update.effective_user else None
        try:
            await update.effective_message.reply_text(translate(language, "provider_error"))
        except TelegramError as error:
            logger.warning("Cannot send error notification (%s).", type(error).__name__)


def build_application(
    settings: Settings,
) -> Application[
    ExtBot[None],
    ContextTypes.DEFAULT_TYPE,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    JobQueue[ContextTypes.DEFAULT_TYPE],
]:
    """Create an application without starting polling or making network requests."""
    assistant = TelegramAssistant(settings)
    application = Application.builder().token(settings.token).concurrent_updates(8).build()
    for command in ("start", "help", "ping", "ask", "providers", "version"):
        application.add_handler(CommandHandler(command, getattr(assistant, command)))
    application.add_error_handler(on_error)
    return application


def main() -> None:
    """Load credentials at startup and run the bot until it is stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="YAML configuration path")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "--check-config", action="store_true", help="Validate local settings without network calls"
    )
    args = parser.parse_args()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    load_dotenv(args.config.parent / ".env")
    try:
        settings = load_config(args.config)
    except (OSError, ValueError, yaml.YAMLError) as error:
        logger.error(
            "Cannot load configuration (%s). Check the config file and .env.", type(error).__name__
        )
        raise SystemExit(1) from None
    if args.check_config:
        print(
            "Configuration is valid. Credentials and provider availability were not checked online."
        )
        return
    logger.info("Starting Telegram AI Bot %s.", VERSION)
    build_application(settings).run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
