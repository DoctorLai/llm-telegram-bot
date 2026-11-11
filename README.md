# Telegram AI Bot

[![CI](https://github.com/doctorlai/llm-telegram-bot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/doctorlai/llm-telegram-bot/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/downloads/)
[![Privacy](https://img.shields.io/badge/privacy-data%20flow-blue)](PRIVACY.md)
[![Security policy](https://img.shields.io/badge/security-policy-blue)](SECURITY.md)
[![Last commit](https://img.shields.io/github/last-commit/doctorlai/llm-telegram-bot/main)](https://github.com/doctorlai/llm-telegram-bot/commits/main)
[![License](https://img.shields.io/github/license/doctorlai/llm-telegram-bot)](LICENSE)
[![Stars](https://img.shields.io/github/stars/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/stargazers)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-d7ff64)](https://docs.astral.sh/ruff/)
[![Commit activity](https://img.shields.io/github/commit-activity/m/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/graphs/commit-activity)
[![Watchers](https://img.shields.io/github/watchers/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/watchers)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)
[![Python percentage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdoctorlai%2Fllm-telegram-bot%2Fbadges%2Fpython.json)](https://github.com/doctorlai/llm-telegram-bot/tree/badges)
[![Repository size](https://img.shields.io/github/repo-size/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot)
[![Top code language](https://img.shields.io/github/languages/top/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot)
[![Bot locales](https://img.shields.io/badge/bot%20locales-25-blue)](lang/README.md)
[![Open PRs](https://img.shields.io/github/issues-pr/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/pulls)
[![Forks](https://img.shields.io/github/forks/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/forks)
[![Open issues](https://img.shields.io/github/issues/doctorlai/llm-telegram-bot)](https://github.com/doctorlai/llm-telegram-bot/issues)
[![Node.js for development](https://img.shields.io/badge/node%20%28dev%29-%3E%3D22-339933)](https://nodejs.org/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/doctorlai/llm-telegram-bot)

A self-hosted Python bot that answers Telegram questions using Grok, OpenAI, or another OpenAI-compatible chat-completions endpoint. **Version: 2026-11-11.**

[Quick start](#quick-start) · [Commands](#commands) · [Configuration](#configuration) · [Build and distribute](#build-and-distribute) · [Development](#development)

The existing public bot is [@justyy_llm_bot](https://t.me/justyy_llm_bot); its availability, deployed version, and privacy practices are controlled by its operator.

## What it does

- `/ask` selects a configured provider or uses the default (Grok).
- `/providers` lists providers with configured keys and their model IDs, without exposing credentials.
- Asynchronous requests have a configurable timeout; users have a configurable cooldown.
- Long replies are split within Telegram's message limit, including emoji and other Unicode text.
- Bot messages follow the user's Telegram language in [25 JSON catalogs](lang/README.md), including separate Simplified and Traditional Chinese translations.
- `/ping` checks connectivity; `/version` reports the date-based application version.
- `--check-config` validates local settings before you start the bot, without contacting any API.

Questions are independent: no conversation history, retry buttons, or memory-clearing buttons are implemented. The bot does not write prompts or answers to its application logs. Telegram and the selected provider still receive message content; read [PRIVACY.md](PRIVACY.md).

## Quick start

You need Python **3.11 or newer**, a [BotFather](https://t.me/BotFather) token, and an API key for your chosen provider. Model names in the sample configuration are examples inherited from the earlier bot; select a model currently available to your provider account.

```bash
git clone https://github.com/doctorlai/llm-telegram-bot.git
cd llm-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` and copy with `Copy-Item .env.example .env`.

Edit `.env` and set:

```dotenv
YOUR_TELEGRAM_BOT_API_TOKEN=your-telegram-token
YOUR_GROK_API_KEY=your-grok-key
YOUR_OPENAI_API_KEY=
```

The default provider is `grok`, so its key is required. To use only OpenAI, set `llms.default_model: openai` in [config.yaml](config.yaml) and supply `YOUR_OPENAI_API_KEY` instead. Unused providers may have empty or unset keys.

```bash
python bot.py --check-config
python bot.py
```

The config check validates required settings, not live credentials or model availability. Running the bot uses long polling; no public HTTP port or webhook is needed. Stop with Ctrl+C. Do not run two polling instances with the same Telegram token.

## Commands

| Command | Behavior |
| --- | --- |
| `/start` | Welcome message and commands |
| `/help` | Command reference |
| `/ping` | Pong and the time taken to send the first reply |
| `/ask What is AI?` | Ask the default provider |
| `/ask openai What is AI?` | Ask the provider named `openai` |
| `/ask grok What is AI?` | Ask the provider named `grok` |
| `/providers` | List configured providers and models; identify the default |
| `/version` | Show the date-based version |

Use `/`, not `!`. A configured provider name at the beginning of a question selects that provider; otherwise the entire text is sent to the default provider. A provider name without a question is rejected without using the cooldown.

`/providers` reads local configuration, not the provider's account API. A listed model can still fail if a key has expired, a quota is exhausted, or the model is unavailable to that account.

In groups, send commands addressed to the bot when needed, such as `/ask@your_bot What is AI?`. Replies are visible to the chat. The application does not implement a user allowlist or a global spending cap; review provider quotas before making a bot public.

## Configuration

[config.yaml](config.yaml) is the configuration source. `${VARIABLE}` references are expanded from the environment. `.env` is loaded from the configuration file's directory without overriding existing environment variables.

An unset variable used as an entire value is treated as missing. Expansion happens once: literal dollar signs in supplied credentials or system prompts are not rejected or interpreted a second time.

| Setting | Meaning |
| --- | --- |
| `telegram.token` | Required Telegram bot token |
| `rate_limit` | Required per-user seconds between nonempty questions; sample value `10`, `0` disables the cooldown |
| `request_timeout` | HTTP timeout in seconds for connect/read/write/pool operations; default `30`, minimum `0.1` |
| `llms.default_model` | Default **provider name**, despite the historical setting name |
| `llms.providers.<name>.api_url` | Full HTTP(S) chat-completions endpoint, including `/v1/chat/completions` |
| `api_key` | Bearer token; required at startup for the default provider |
| `model` | Model ID accepted by that provider |
| `role` | System message sent with each question |
| `temperature` | Number between `0` and `2`; provider-specific limits may be narrower |
| `max_tokens` | Positive integer output-token limit |

Provider names must be lowercase and contain no spaces. Both built-in providers use the same chat-completions request format. The OpenAI URL defaults to `https://api.openai.com/v1/chat/completions`; custom gateways must be configured explicitly. Changing this URL changes who receives your key and prompts.

The HTTP timeout is an inactivity timeout per network operation, not a hard end-to-end deadline. Failed provider requests still use the cooldown to limit repeated paid requests. Expired cooldown entries are pruned on the next nonempty question.

Use another configuration file or print the version without credentials:

```bash
python bot.py --config /path/to/config.yaml
python bot.py --config /path/to/config.yaml --check-config
python bot.py --version
```

## Build and distribute

This repository is a Telegram bot, **not a Chrome extension**. There is no browser manifest, Web Store listing, user count, or rating. Its ZIP is a source distribution for self-hosting, not a Web Store upload.

With the development environment below installed:

```bash
npm run build       # source ZIP + SHA-256 checksum + Docker image
npm run build:zip   # source ZIP + checksum only; no Docker required
```

Outputs are `dist/llm-telegram-bot-2026-11-11.zip`, its `.zip.sha256` checksum, and the Docker image `llm-telegram-bot:local`. The [CI build](.github/workflows/ci.yml) makes only the ZIP and checksum available as downloadable artifacts; it does not upload coverage reports.

The archive includes runtime code, all translations, configuration templates, docs, and development tools/tests. Files are allowlisted; `.env`, Git metadata, virtual environments, caches, and coverage output are excluded. The build rejects symlinks and literal credentials in `config.yaml`. Review source files before distributing them: this is not a general-purpose secret scanner.

Extract the ZIP into a new directory, then follow Quick start from the virtual-environment step instead of cloning. Python dependencies are not bundled. On Linux, verify the downloaded files with:

```bash
sha256sum --check llm-telegram-bot-2026-11-11.zip.sha256
```

## Docker

```bash
docker build -t llm-telegram-bot .
docker run --rm --name llm-telegram-bot \
  --env-file .env \
  --mount type=bind,source="$(pwd)/config.yaml",target=/app/config.yaml,readonly \
  llm-telegram-bot
```

The image uses Python 3.11 and an unprivileged user. Only runtime files are copied into it; `.env`, tests, Git metadata, and coverage reports are excluded. Keep credentials in the runtime environment, not literal YAML values or the image. Add `-d --restart unless-stopped` and omit `--rm` for a persistent deployment.

There is no browser UI, dark-mode CSS, browser storage, or GitHub Pages deployment.

## Development

The npm commands use an activated virtual environment when present, otherwise the project's `.venv`, then `python3` or `python` on `PATH`. Activation is not required when using `.venv`; no system `python` alias is needed. Node.js is only a task runner, not a bot dependency. Node 22+ is supported; [.nvmrc](.nvmrc) selects Node 24.

```bash
python3 -m venv .venv    # once, if you have not created it already
.venv/bin/python -m pip install -r requirements-dev.txt
nvm use                 # optional, if nvm is installed
npm ci                  # no npm dependencies
npm run check           # all checks + ZIP + Docker build
```

On Windows, create the environment with `py -3 -m venv .venv` and install with `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`. npm does not install Python dependencies. Native Python commands outside npm still require activation or an explicit interpreter path.

| Command | Checks / action |
| --- | --- |
| `npm run format` | Format Python and apply Ruff fixes |
| `npm run format:check` | Check formatting without changing files |
| `npm run lint` | Ruff and strict mypy |
| `npm run test` | Offline tests with mocked provider and Telegram APIs |
| `npm run coverage` | Tests, HTML/XML/JSON reports, and minimum 80% for each metric |
| `npm run build` | Build the source ZIP/checksum and runnable Docker image |
| `npm run build:zip` | Build only the source ZIP/checksum |
| `npm run build:docker` | Build only the Docker image |
| `npm run check` | Formatting, lint, types, tests, coverage, ZIP, and Docker build |
| `npm run ci` | Alias for the full check; distinct from the `npm ci` install command |
| `npm run check:python` | All Python checks without requiring Docker |
| `npm run config:check` | Validate local bot configuration without network calls |
| `npm start` | Run the bot |

See [CONTRIBUTING.md](CONTRIBUTING.md) for native Python commands, translation checks, and GitHub permissions. CI tests Python 3.11, 3.12, 3.13, and 3.14. Coverage remains a local/CI pass-fail gate: at least 80% for each measured metric. There are no coverage uploads, PR coverage comments, or README coverage badges.

The dynamic Python-percentage badge is generated from GitHub language byte counts and committed only to the `badges` branch. It becomes available after the first successful Badges workflow on `main`; no automated commit is made to protected `main`. The top-language badge describes source code, not human translations.

## Project information

- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Support](SUPPORT.md)
- [Security policy](SECURITY.md)
- [Privacy and data flow](PRIVACY.md)
- [MIT license](LICENSE)

## Support the maintainer

- [Buy me a coffee](https://justyy.com/out/bmc)
- [Sponsor on GitHub](https://github.com/sponsors/DoctorLai)
- [Vote for the maintainer as a Steem witness](https://steemyy.com/witness-voting/?witness=justyy&action=approve)
- [Set a Steem witness proxy](https://steemyy.com/witness-voting/?witness=justyy&action=proxy)
