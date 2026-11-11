# Changelog

Application versions use UTC dates (`YYYY-MM-DD`). There is no npm or PyPI release process; the npm manifest provides development shortcuts only.

## 2026-11-11

### Added

- Ruff formatting/linting, strict mypy, offline pytest tests, and an independent 80% gate for line, statement, function-entry, and branch coverage.
- npm shortcuts for formatting, linting, tests, coverage, ZIP/Docker builds, offline configuration validation, and combined checks (`check` / `ci`).
- Reproducible source ZIPs and SHA-256 checksums in `dist/`, with allowlisted files and checks against symlinks and literal config credentials.
- Read-only PR CI with local coverage gates, downloadable source ZIPs, and a dynamic Python-percentage badge on the `badges` branch. Coverage reports are not uploaded or posted, and there is no coverage badge.
- Python 3.11-3.14 CI matrix, SHA-pinned actions, and weekly Dependabot updates.
- 25 JSON message catalogs using Telegram language preferences, with separate Simplified and Traditional Chinese catalogs.
- `/providers` to discover configured providers and model IDs, without exposing credentials or using the question cooldown.
- `/version` and `--version`, offline `--check-config`, `--config`, and configurable HTTP request timeouts.
- Contributor, support, security, privacy, and translation documentation; PR/bug templates and repository hygiene files.

### Fixed

- npm commands resolve the active/project virtual environment or `python3`/`python` automatically, so they work on systems without a `python` alias.
- Replaced the invalid OpenAI completions call and blocking HTTP calls with asynchronous OpenAI-compatible chat requests.
- Added startup configuration validation and allowed unused providers to omit credentials.
- Preserve literal dollar signs in API keys and system prompts while still detecting unset whole-value environment references.
- Reject empty questions after provider selection without consuming the cooldown.
- Split long responses within Telegram's UTF-16 message limit without splitting Unicode characters.
- A failed typing indicator is logged without aborting the question; failed error notifications are also logged without exposing raw exceptions.
- Removed unused conversation retention and logging of prompts, answers, and raw provider exceptions.
- Removed README claims about unimplemented retry buttons, memory controls, and chat continuity; corrected command syntax and clone/setup instructions.

### Changed

- Python 3.11+ is now required, matching the existing Docker runtime. Python 3.8-3.10 are no longer supported.
- Updated the Telegram client and removed the obsolete OpenAI SDK, requests, and unused aiohttp dependencies.
- The sample OpenAI endpoint now points directly to OpenAI, not a third-party gateway. Set `api_url` explicitly if you intentionally use a gateway.
- Docker copies only runtime files and runs as an unprivileged user.
- Grok remains the default provider and the sample cooldown remains 10 seconds. Provider failures still consume that cooldown.
