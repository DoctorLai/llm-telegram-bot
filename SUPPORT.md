# Support

Start with [README.md](README.md) for setup and [CONTRIBUTING.md](CONTRIBUTING.md) for development. Use the repository's [issues](https://github.com/doctorlai/llm-telegram-bot/issues) for reproducible bugs and feature requests. Support is volunteer-based; no uptime or response-time commitment is provided.

For the public bot, deployment settings and availability are controlled by its operator. Installing this repository does not connect you to that deployment.

## Common problems

| Symptom | Check |
| --- | --- |
| Startup says configuration cannot be loaded | Run `python bot.py --check-config`. Check YAML syntax, `.env` beside the selected config, the Telegram token, and the default provider's key. Placeholder `${...}` values must resolve. The check is offline and cannot validate credentials against an API. |
| OpenAI works but Grok does not, or vice versa | Verify the selected provider's key, full chat-completions URL, and a model available to that account. The default provider is `grok`. |
| Unsure which providers are configured | Use `/providers`. It lists provider/model names with configured keys, not live account availability. |
| `/ask` reports that the request failed | Check account quotas, model availability, network reachability, and `request_timeout`. Logs include the error category, not private response bodies. |
| A command appears ignored | Use `/ask`, not `!ask`; in groups try `/ask@your_bot`. Confirm the bot's group permissions and that exactly one process is polling its token. |
| The bot asks you to wait | `rate_limit` is measured per user across chats. Failed provider attempts also use the cooldown; `/ping`, `/help`, `/providers`, and empty questions do not. |
| Replies do not remember earlier messages | Conversation history is intentionally not implemented. Include relevant context in the current question. |
| Bot interface language is unexpected | The bot uses Telegram's user language, falls back to English, and maps Chinese variants as documented in [lang/README.md](lang/README.md). LLM answer language is controlled by the prompt and provider. |
| An npm command cannot find Python | Install Python 3.11+ and create `.venv` with `python3 -m venv .venv` (`py -3 -m venv .venv` on Windows). npm selects the active virtual environment, project `.venv`, then `python3`/`python` on `PATH`. |
| An npm command cannot import a Python package | Install `requirements-dev.txt` into the selected environment; for the project environment, use `.venv/bin/python -m pip install -r requirements-dev.txt` (`.\.venv\Scripts\python.exe` on Windows). npm does not install Python dependencies or switch interpreters after a command fails. |
| `npm run check` fails at the Docker build | Ensure Docker is installed and its daemon is available. `npm run check:python` runs checks without Docker; `npm run build:zip` creates the ZIP independently. |
| ZIP build rejects the configuration | Use `${VARIABLE}` references for credentials in `config.yaml`, not literal keys or tokens. Check that release files are present and are not symlinks. |
| ZIP cannot be uploaded to the Chrome Web Store | This is a Python Telegram bot source distribution, not a browser extension. Extract it and follow the Python or Docker setup instructions. |
| No PR coverage report or badge | This is intentional. Coverage is enforced by `npm run coverage`, `npm run check`, and CI, but reports are not uploaded or posted. |
| Python-percentage badge says unavailable | Run the Badges workflow on `main`; allow writes to `badges`. GitHub Linguist statistics and Shields responses can be cached. |

## Filing a useful issue

Include:

- `python bot.py --version` and `python --version`;
- OS and whether you use Docker;
- provider name and a minimal reproduction with dummy input;
- the expected result and the logged error category;
- which checks you ran.

Do not attach `.env`, API keys, bot tokens, private prompts, or unredacted provider responses. For vulnerabilities, follow [SECURITY.md](SECURITY.md) instead.
