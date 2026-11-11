import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

import pytest
import yaml

import bot
from scripts import build_release


@pytest.fixture
def release_source(tmp_path):
    source = tmp_path / "source"
    files = {build_release.ROOT / name for name in build_release.ROOT_FILES}
    for pattern in build_release.SOURCE_PATTERNS:
        files.update(build_release.ROOT.glob(pattern))
    for path in files:
        target = source / path.relative_to(build_release.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return source


def test_archive_is_complete_reproducible_and_excludes_local_data(release_source, tmp_path):
    private_text = f"not-for-distribution-{tmp_path.name}"
    for name in (
        ".env",
        ".env.production",
        "private.key",
        "coverage.json",
        "coverage-report.json",
        "htmlcov/index.html",
        ".git/config",
        ".venv/token",
        "node_modules/private.js",
        "lang/.env",
        "scripts/__pycache__/private.pyc",
    ):
        path = release_source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(private_text, encoding="utf-8")
    output = tmp_path / "dist"
    archive = build_release.build_release(release_source, output)
    first_bytes = archive.read_bytes()
    assert archive.name == f"llm-telegram-bot-{bot.VERSION}.zip"
    digest, filename = archive.with_suffix(".zip.sha256").read_text().split()
    assert digest == hashlib.sha256(first_bytes).hexdigest()
    assert filename == archive.name
    with ZipFile(archive) as release:
        assert release.testzip() is None
        names = release.namelist()
        assert names == sorted(names)
        assert set(build_release.ROOT_FILES).issubset(names)
        assert (
            len([name for name in names if name.startswith("lang/") and name.endswith(".json")])
            == 25
        )
        for entry in release.infolist():
            assert not Path(entry.filename).is_absolute()
            assert ".." not in Path(entry.filename).parts
            assert stat.S_IMODE(entry.external_attr >> 16) == 0o644
            assert private_text.encode() not in release.read(entry)
    os.utime(release_source / "bot.py", (1000000000, 1000000000))
    (release_source / "bot.py").chmod(0o600)
    assert build_release.build_release(release_source, output).read_bytes() == first_bytes
    assert not list(output.glob(".release-*"))


def test_unpacked_archive_runs_without_git_and_preserves_doc_links(release_source, tmp_path):
    archive = build_release.build_release(release_source, tmp_path / "dist")
    extracted = tmp_path / "extracted"
    with ZipFile(archive) as release:
        release.extractall(extracted)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment.update(
        YOUR_TELEGRAM_BOT_API_TOKEN="123456:offline-test",
        YOUR_GROK_API_KEY="offline-test-key",
        YOUR_OPENAI_API_KEY="",
    )
    for flag, expected in [
        ("--version", bot.VERSION),
        ("--check-config", "Configuration is valid."),
    ]:
        result = subprocess.run(
            [sys.executable, str(extracted / "bot.py"), flag],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        assert expected in result.stdout
        assert "offline-test-key" not in result.stdout + result.stderr
    for doc in extracted.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", doc.read_text(encoding="utf-8")):
            link = urlsplit(target)
            if not link.scheme and link.path:
                assert (doc.parent / unquote(link.path)).exists(), (doc.name, target)


@pytest.mark.parametrize(
    "source",
    [
        "VERSION = '2026-11-11'",
        "import os\nVERSION = '2026-11-11'\nraise RuntimeError('must not execute')",
    ],
)
def test_version_reading_never_executes_code(source):
    assert build_release.release_version(source) == "2026-11-11"


@pytest.mark.parametrize(
    "source",
    ["", "VERSION = 123", "VERSION = '2026-11-31'", "VERSION = '20261111'", "VERSION = input()"],
)
def test_invalid_release_versions_fail(source):
    with pytest.raises(ValueError):
        build_release.release_version(source)


@pytest.mark.parametrize("value", ["literal-secret", 123, False])
def test_packaging_refuses_literal_credentials(release_source, tmp_path, value):
    config = yaml.safe_load((release_source / "config.yaml").read_text(encoding="utf-8"))
    config["llms"]["providers"]["grok"]["api_key"] = value
    (release_source / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="environment-variable references"):
        build_release.build_release(release_source, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize("value", [None, "", "$API_KEY", "${API_KEY}"])
def test_config_template_allows_placeholders_or_disabled_keys(config_data, value):
    config_data["llms"]["providers"]["openai"]["api_key"] = value
    build_release.validate_config_template(yaml.safe_dump(config_data))


@pytest.mark.parametrize("contents", ["[]", "{}", "llms:\n  providers: []\ntelegram:\n  token: ''"])
def test_malformed_template_is_rejected(contents):
    with pytest.raises(ValueError, match="expected Telegram/provider"):
        build_release.validate_config_template(contents)


def test_missing_release_file_fails_without_replacing_existing_output(release_source, tmp_path):
    archive = build_release.build_release(release_source, tmp_path / "dist")
    original = archive.read_bytes()
    (release_source / "bot.py").unlink()
    with pytest.raises(FileNotFoundError, match="bot.py"):
        build_release.build_release(release_source, tmp_path / "dist")
    assert archive.read_bytes() == original


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_symlinks_are_not_distributed(release_source, tmp_path, kind):
    try:
        if kind == "file":
            target = release_source / "bot.py"
            target.unlink()
            target.symlink_to(build_release.ROOT / "bot.py")
        else:
            (release_source / "scripts").rename(release_source / "original-scripts")
            (release_source / "scripts").symlink_to(
                release_source / "original-scripts", target_is_directory=True
            )
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Creating symlinks requires elevated privileges on this Windows system.")
        raise
    with pytest.raises(ValueError, match="symlink"):
        build_release.build_release(release_source, tmp_path / "dist")


def test_failed_archive_write_preserves_previous_release(release_source, tmp_path, monkeypatch):
    output = tmp_path / "dist"
    archive = build_release.build_release(release_source, output)
    original = archive.read_bytes()
    real_read = Path.read_bytes

    def fail_on_locale(path):
        if path.name == "en.json":
            raise OSError("simulated read failure")
        return real_read(path)

    monkeypatch.setattr(Path, "read_bytes", fail_on_locale)
    with pytest.raises(OSError, match="simulated"):
        build_release.build_release(release_source, output)
    assert archive.read_bytes() == original
    assert not list(output.glob(".release-*"))


def test_build_command(release_source, tmp_path, monkeypatch, capsys):
    output = tmp_path / "custom-dist"
    monkeypatch.setattr(build_release, "ROOT", release_source)
    monkeypatch.setattr(sys, "argv", ["build_release", "--output", str(output)])
    build_release.main()
    assert (output / f"llm-telegram-bot-{bot.VERSION}.zip").is_file()
    assert "Built" in capsys.readouterr().out


def test_build_command_reports_failure_without_echoing_credentials(
    release_source, tmp_path, monkeypatch, capsys
):
    (release_source / "config.yaml").write_text("telegram: [secret-to-hide", encoding="utf-8")
    monkeypatch.setattr(build_release, "ROOT", release_source)
    monkeypatch.setattr(sys, "argv", ["build_release", "--output", str(tmp_path / "dist")])
    with pytest.raises(SystemExit) as error:
        build_release.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Cannot build release" in captured.err
    assert "secret-to-hide" not in captured.err
