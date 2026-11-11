"""Build a reproducible source ZIP without environment files or local artifacts."""

import argparse
import ast
import hashlib
import re
import stat
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    ".nvmrc",
    ".python-version",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "Dockerfile",
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "bot.py",
    "config.yaml",
    "localization.py",
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "lang/README.md",
    "scripts/run-python.cjs",
)
SOURCE_PATTERNS = (
    "lang/*.json",
    "scripts/*.py",
    "tests/*.py",
    ".github/*.yml",
    ".github/*.md",
    ".github/ISSUE_TEMPLATE/*.yml",
    ".github/ISSUE_TEMPLATE/*.md",
    ".github/workflows/*.yml",
)


def release_version(source: str) -> str:
    """Read the date version without importing or executing the application."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets
        ):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                version = node.value.value
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", version):
                    return date.fromisoformat(version).isoformat()
    raise ValueError("bot.py must define VERSION as a literal YYYY-MM-DD date.")


def validate_config_template(contents: str) -> None:
    """Refuse to distribute literal credentials in the bundled YAML configuration."""
    config = yaml.safe_load(contents)
    try:
        credentials = [config["telegram"]["token"]]
        credentials.extend(
            provider.get("api_key") for provider in config["llms"]["providers"].values()
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(
            "config.yaml does not contain the expected Telegram/provider settings."
        ) from error
    for value in credentials:
        if (
            value is not None
            and value != ""
            and (
                not isinstance(value, str)
                or not re.fullmatch(r"\$(?:\{[A-Za-z_]\w*\}|[A-Za-z_]\w*)", value)
            )
        ):
            raise ValueError(
                "config.yaml must use environment-variable references "
                "for credentials before packaging."
            )


def build_release(source: Path, output: Path) -> Path:
    """Package allowlisted source files with fixed metadata and a SHA-256 sidecar."""
    source = source.resolve()
    files = {source / name for name in ROOT_FILES}
    for pattern in SOURCE_PATTERNS:
        files.update(source.glob(pattern))
    for path in files:
        if path.is_symlink() or any(
            parent.is_symlink() for parent in path.parents if parent.is_relative_to(source)
        ):
            raise ValueError(f"Refusing to package a symlink: {path.relative_to(source)}")
        if not path.is_file():
            raise FileNotFoundError(f"Required release file is missing: {path.relative_to(source)}")
    validate_config_template((source / "config.yaml").read_text(encoding="utf-8"))
    version = release_version((source / "bot.py").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"llm-telegram-bot-{version}.zip"
    with NamedTemporaryFile(dir=output, prefix=".release-", suffix=".zip", delete=False) as file:
        temporary = Path(file.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(files, key=lambda path: path.relative_to(source).as_posix()):
                info = ZipInfo(path.relative_to(source).as_posix())
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes())
        temporary.replace(archive_path)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix(".zip.sha256").write_text(
        f"{digest}  {archive_path.name}\n", encoding="utf-8"
    )
    return archive_path


def main() -> None:
    """Create the deployment ZIP in dist, or an explicitly selected output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        archive = build_release(ROOT, args.output)
    except (OSError, ValueError, SyntaxError, yaml.YAMLError) as error:
        parser.exit(
            1,
            f"Cannot build release ({type(error).__name__}). "
            "Check release files, config credential placeholders, and output permissions.\n",
        )
    print(f"Built {archive} and {archive.name}.sha256")


if __name__ == "__main__":
    main()
