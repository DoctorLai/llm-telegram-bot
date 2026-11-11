"""Resolve Telegram language codes to bundled, UTF-8 message catalogs."""

import json
from functools import lru_cache
from pathlib import Path

LANG_DIR = Path(__file__).with_name("lang")
SUPPORTED_LOCALES = (
    "ar",
    "bn",
    "de",
    "en",
    "es",
    "fr",
    "hi",
    "id",
    "it",
    "ja",
    "ko",
    "mr",
    "nl",
    "pa",
    "pl",
    "pt",
    "ru",
    "ta",
    "te",
    "th",
    "tr",
    "ur",
    "vi",
    "zh-CN",
    "zh-TW",
)


def resolve_locale(language_code: str | None) -> str:
    """Use a supported regional locale, base language, or English fallback."""
    normalized = (language_code or "en").replace("_", "-").lower()
    parts = normalized.split("-")
    if parts[0] == "zh":
        return "zh-TW" if {"hant", "tw", "hk", "mo"}.intersection(parts) else "zh-CN"
    return parts[0] if parts[0] in SUPPORTED_LOCALES else "en"


@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def _catalog(locale: str) -> dict[str, str]:
    with (LANG_DIR / f"{locale}.json").open(encoding="utf-8") as file:
        messages = json.load(file)
    if not isinstance(messages, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in messages.items()
    ):
        raise ValueError(f"Invalid translation catalog: {locale}")
    return messages


def translate(language_code: str | None, key: str, **values: object) -> str:
    """Format a translated message; missing keys are errors, not silent fallbacks."""
    return _catalog(resolve_locale(language_code))[key].format(**values)
