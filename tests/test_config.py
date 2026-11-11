import os
import subprocess
import sys
from copy import deepcopy

import pytest
import yaml

import bot


def test_recursive_environment_expansion(monkeypatch):
    monkeypatch.setenv("TEST_VALUE", "expanded")
    value = {"items": ["${TEST_VALUE}", {"literal": 12}], "flag": True, "empty": None}
    original = deepcopy(value)
    assert bot.expand_env_vars(value) == {
        "items": ["expanded", {"literal": 12}],
        "flag": True,
        "empty": None,
    }
    assert value == original


def test_sample_config_defaults_and_optional_provider(config_path, monkeypatch):
    monkeypatch.delenv("YOUR_OPENAI_API_KEY")
    settings = bot.load_config(config_path)
    assert settings.default_model == "grok"
    assert settings.rate_limit == 10
    assert settings.request_timeout == 30
    assert settings.providers["grok"].api_key == "test-grok-key"
    assert settings.providers["openai"].api_key == ""
    assert settings.providers["openai"].api_url == "https://api.openai.com/v1/chat/completions"


@pytest.mark.parametrize("variable", ["YOUR_TELEGRAM_BOT_API_TOKEN", "YOUR_GROK_API_KEY"])
def test_required_credentials_fail_at_startup(config_path, monkeypatch, variable):
    monkeypatch.delenv(variable)
    with pytest.raises(ValueError, match="must be set"):
        bot.load_config(config_path)


def test_defaults_and_literal_dollar_in_system_prompt(config_path, config_data):
    config_data.pop("request_timeout")
    config_data["llms"]["providers"]["grok"]["role"] = "Explain prices such as $5."
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    settings = bot.load_config(config_path)
    assert settings.request_timeout == 30
    assert settings.providers["grok"].role == "Explain prices such as $5."


@pytest.mark.parametrize(
    ("path", "value", "error"),
    [
        (("telegram",), [], "mapping"),
        (("telegram", "token"), 123, "must be set"),
        (("llms", "default_model"), "unknown", "configured provider"),
        (("llms", "providers"), [], "mapping"),
        (("llms", "providers"), {1: {}}, "string keys"),
        (("llms", "providers", "grok"), [], "mapping"),
        (("rate_limit",), -1, "finite number"),
        (("rate_limit",), True, "finite number"),
        (("rate_limit",), float("inf"), "finite number"),
        (("rate_limit",), float("nan"), "finite number"),
        (("rate_limit",), "ten", "finite number"),
        (("request_timeout",), 0, "finite number"),
        (("llms", "providers", "grok", "temperature"), 2.1, "finite number"),
        (("llms", "providers", "grok", "max_tokens"), 0, "positive integer"),
        (("llms", "providers", "grok", "max_tokens"), 1.5, "positive integer"),
        (("llms", "providers", "grok", "max_tokens"), True, "positive integer"),
        (("llms", "providers", "grok", "model"), "", "must be set"),
        (("llms", "providers", "grok", "api_url"), "ftp://example.com", "HTTP"),
        (("llms", "providers", "grok", "api_url"), "https://", "HTTP"),
        (("llms", "providers", "grok", "api_key"), None, "must be set"),
        (("llms", "providers", "openai", "api_key"), 0, "api_key"),
    ],
)
def test_invalid_configuration(config_path, config_data, path, value, error):
    target = config_data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        bot.load_config(config_path)


@pytest.mark.parametrize("name", ["", "OpenAI", "two words"])
def test_invalid_provider_names(config_path, config_data, name):
    config_data["llms"]["providers"][name] = config_data["llms"]["providers"].pop("openai")
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    with pytest.raises(ValueError, match="lowercase words"):
        bot.load_config(config_path)


@pytest.mark.parametrize("value", [None, "", "   ", "${MISSING_KEY}"])
def test_optional_credentials_can_be_omitted(config_path, config_data, value):
    config_data["llms"]["providers"]["openai"]["api_key"] = value
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    assert bot.load_config(config_path).providers["openai"].api_key == ""


@pytest.mark.parametrize("contents", ["", "[]", "telegram: ["])
def test_invalid_yaml(config_path, contents):
    config_path.write_text(contents, encoding="utf-8")
    with pytest.raises((ValueError, yaml.YAMLError)):
        bot.load_config(config_path)


def test_import_needs_no_tokens_or_configuration(tmp_path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"YOUR_TELEGRAM_BOT_API_TOKEN", "YOUR_OPENAI_API_KEY", "YOUR_GROK_API_KEY"}
    }
    environment["PYTHONPATH"] = str(bot.CONFIG_PATH.parent)
    result = subprocess.run(
        [sys.executable, "-c", "import bot; print(bot.VERSION)"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == bot.VERSION
    assert result.stderr == ""
