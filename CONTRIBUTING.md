# Contributing

Bug fixes, regression tests, documentation corrections, and translation improvements are welcome. For changes to provider behavior or deployment requirements, open an issue before a large implementation.

## Local setup

Use Python 3.11+ and a virtual environment. Node 22+ is optional for the npm shortcuts; [.nvmrc](.nvmrc) recommends Node 24. Docker is needed for the full build, but not for `npm run build:zip`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci
npm run check
```

npm commands automatically select the active virtual environment, the project's `.venv`, or `python3`/`python` on `PATH`, in that order. You do not need to activate `.venv` or create a system `python` alias. On Windows, use `py -3 -m venv .venv` and `.\.venv\Scripts\python.exe` for installation.

Tests use dummy credentials and mocked HTTP/Telegram calls. They do not require a bot token, provider keys, or network access. The initial dependency install and Docker base-image download require network access. Launcher regression tests use Node.js and are skipped in native pytest runs when Node is unavailable.

## Quality commands

Run `npm run format` before submitting changes. `npm run check` performs non-mutating formatting checks, Ruff, strict mypy, tests with coverage, source ZIP/checksum creation, and the Docker build. `npm run ci` is an alias for that full check; `npm ci` installs the npm manifest/lockfile.

Without npm, activate `.venv` first and run the Python commands directly:

```bash
source .venv/bin/activate
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest
python -m scripts.coverage_report
python -m scripts.build_release
docker build --tag llm-telegram-bot:local .
```

`npm run check:python` omits the Docker and production artifact build steps; its tests still verify ZIP packaging in temporary directories. The badge-branch integration test requires POSIX Bash and Git and is skipped when those prerequisites are unavailable. Keep runtime code compatible with Python 3.11, even when developing on a newer interpreter.

## Tests

Test observable behavior: provider payloads, errors, timeouts, command routing, concurrent questions, cooldown boundaries, Unicode message limits, translations, offline config validation, archive contents, and coverage enforcement. Do not make paid provider calls. The polling integration test mocks HTTP transport while exercising the real application startup and shutdown.

New provider integrations should use the existing asynchronous chat-completions client when compatible. Keep logs free of credentials, URLs containing credentials, prompts, and provider responses. Missing configuration and failed requests must be visible to the operator or user without exposing those details.

## Coverage and CI

`npm run coverage` produces `coverage.json`, `coverage.xml`, `coverage-report.json`, and `htmlcov/`. All are ignored by Git.

Each metric must independently reach **80%**, using unrounded values:

- **Lines / statements:** coverage.py executable statement counts; these are the same metric in Python.
- **Functions:** functions with at least one executed body statement, excluding module-level and fully excluded bodies. This does not imply every path within a function was tested.
- **Branches:** executed branch destinations.

Zero-item function or branch metrics are treated as 100%; a report with no executable statements is rejected. The standard coverage.py combined gate is also 80%. Do not exclude code merely to reach the threshold.

The [CI workflow](.github/workflows/ci.yml) runs with a read-only token. It enforces coverage in test jobs without uploading reports, posting PR comments, or publishing a coverage badge. Its build job uploads only the source ZIP and checksum.

### Maintainer setup

1. Enable GitHub Actions and merge the workflows into `main`.
2. Allow the Badges job's `contents: write` permission and writes to the `badges` branch. Keep `main` protected.
3. Run **Badges** from `main`, or wait for a push to `main`. The Python-percentage badge will appear after that run.
4. Enable private vulnerability reporting in the repository's security settings if it is not already enabled.

No personal access token or third-party coverage account is required. PR jobs receive no write token. Dependabot checks pinned Python dependencies, Docker, and SHA-pinned GitHub Actions weekly. There are no npm dependencies to update.

## Packaging

`npm run build` preserves the Docker build and adds a reproducible source ZIP with a SHA-256 checksum in `dist/`. `npm run build:zip` does not require Docker or Git and can also run from an extracted source ZIP.

The build uses explicit root-file and directory-pattern allowlists in [scripts/build_release.py](scripts/build_release.py). When adding a runtime asset, include it in both the ZIP and [Dockerfile](Dockerfile), and test the packaged behavior. Release validation rejects symlinks and literal token/key values in [config.yaml](config.yaml); keep credentials in environment variables.

ZIP entries use fixed timestamps and file permissions. Rebuilding unchanged source with the same toolchain produces identical ZIP bytes. A failed archive write leaves the previous ZIP intact. The bundle includes all documentation link targets and development files, but no installed dependencies.

## Translations

See [lang/README.md](lang/README.md). Every locale must have the same keys and format placeholders as English. Keep `/start`, `/help`, `/ping`, `/ask`, `/providers`, and `/version` unchanged. The tests validate all catalogs and their Telegram message lengths.

## Pull requests and versions

Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md), describe behavior changes, and include relevant tests. Update [CHANGELOG.md](CHANGELOG.md), user-facing documentation, and `VERSION` in [bot.py](bot.py) for user-visible changes. Versions are UTC date strings (`YYYY-MM-DD`); this application is not published to npm or PyPI.

Do not commit `.env`, tokens, private conversations, generated coverage, or virtual environments. Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.
