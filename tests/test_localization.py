import json
from string import Formatter

import pytest

import localization


@pytest.mark.parametrize(
    ("code", "locale"),
    [
        (None, "en"),
        ("", "en"),
        ("en-US", "en"),
        ("pt_BR", "pt"),
        ("ES-mx", "es"),
        ("zh", "zh-CN"),
        ("zh-Hans-CN", "zh-CN"),
        ("zh-CN", "zh-CN"),
        ("zh-TW", "zh-TW"),
        ("zh_HK", "zh-TW"),
        ("zh-MO", "zh-TW"),
        ("zh-Hant-HK", "zh-TW"),
        ("unknown", "en"),
        ("../../etc/passwd", "en"),
    ],
)
def test_locale_resolution(code, locale):
    assert localization.resolve_locale(code) == locale


def test_all_25_catalogs_have_matching_keys_placeholders_and_valid_messages():
    files = {path.stem for path in localization.LANG_DIR.glob("*.json")}
    assert files == set(localization.SUPPORTED_LOCALES)
    assert len(files) == 25
    reference = json.loads((localization.LANG_DIR / "en.json").read_text(encoding="utf-8"))
    formatter = Formatter()
    for locale in files:
        catalog = json.loads((localization.LANG_DIR / f"{locale}.json").read_text(encoding="utf-8"))
        assert catalog.keys() == reference.keys()
        for key, text in catalog.items():
            assert isinstance(text, str) and text.strip()
            fields = {field for _, field, _, _ in formatter.parse(text) if field}
            expected = {field for _, field, _, _ in formatter.parse(reference[key]) if field}
            assert fields == expected, (locale, key)
            translated = localization.translate(
                locale,
                key,
                seconds=10,
                milliseconds="12.34",
                version="2026-11-11",
                default="grok",
                providers="grok: example-model",
            )
            assert len(translated.encode("utf-16-le")) // 2 <= 4096
        assert "/ask" in catalog["help"]
        assert "/providers" in catalog["help"]
    assert localization.translate("zh-CN", "help") != localization.translate("zh-TW", "help")


@pytest.mark.parametrize("contents", ['["not a mapping"]', '{"help": 1}'])
def test_invalid_catalogs_are_not_silently_ignored(tmp_path, monkeypatch, contents):
    (tmp_path / "en.json").write_text(contents, encoding="utf-8")
    monkeypatch.setattr(localization, "LANG_DIR", tmp_path)
    localization._catalog.cache_clear()
    try:
        with pytest.raises(ValueError, match="Invalid translation"):
            localization.translate("en", "help")
    finally:
        localization._catalog.cache_clear()


def test_missing_translation_is_an_error():
    with pytest.raises(KeyError):
        localization.translate("en", "not-a-message")
