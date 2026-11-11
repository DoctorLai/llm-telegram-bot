# Security policy

## Supported versions

Security fixes target the current code on `main`. Older commits and deployed public bots are not maintained as separate release lines. Python 3.11+ is required; CI covers Python 3.11 through 3.14.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/doctorlai/llm-telegram-bot/security/advisories/new) when it is enabled. If the private-report form is unavailable, contact the maintainer through their [GitHub profile](https://github.com/DoctorLai) to request a private reporting channel. Do not put vulnerability details, credentials, or private conversations in a public issue.

Include the affected commit or date-based version, prerequisites, impact, and reproduction steps using dummy credentials. This is a volunteer-maintained project; there is no guaranteed response time.

## Operating safely

- Keep Telegram tokens and provider keys in `.env` or runtime secrets, never committed YAML or container images.
- Before sharing a ZIP, review its source/configuration templates. Packaging excludes `.env` files and refuses literal config credentials, but cannot detect secrets placed elsewhere in source files.
- Rotate a Telegram token through BotFather and revoke provider keys immediately if exposed. Removing a secret from the latest commit does not remove it from Git history.
- Use HTTPS for remote provider endpoints. A custom endpoint receives the configured API key, system instruction, and question.
- Set provider-side budgets and quotas before making a bot public. Per-user cooldowns are not authentication or a global cost limit.
- Run one polling process per Telegram token. Keep dependencies and the base image updated.
- Do not enable HTTP debug logging in production without checking for token and message exposure.
- Treat model output as untrusted text. The application does not execute it or render it as Telegram HTML/Markdown.

The container runs as an unprivileged user. PR tests and builds use read-only repository permissions. Only the main-branch Badges job requests write access, and it pushes to `badges`, not `main`. These measures do not replace review of changes before merging.
