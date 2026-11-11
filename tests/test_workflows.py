import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def load_workflow(name):
    return yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_workflow_permission_boundaries_and_action_pins():
    ci = load_workflow("ci.yml")
    assert ci["permissions"] == {"contents": "read"}
    assert "pull_request_target" not in ci["on"]
    badges = load_workflow("badges.yml")
    assert "pull_request" not in badges["on"]
    assert badges["jobs"]["update"]["if"] == "github.ref == 'refs/heads/main'"
    for path in WORKFLOWS.glob("*.yml"):
        workflow = load_workflow(path.name)
        assert "workflow_run" not in workflow["on"]
        for job in workflow["jobs"].values():
            assert job.get("permissions", {}).get("pull-requests") != "write"
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", step["uses"])
                if "upload-artifact" in step.get("uses", ""):
                    assert set(step["with"]["path"].splitlines()) == {
                        "dist/llm-telegram-bot-*.zip",
                        "dist/llm-telegram-bot-*.zip.sha256",
                    }


def test_ci_runs_quality_gate_and_builds_the_zip_and_container():
    ci = load_workflow("ci.yml")
    assert ci["jobs"]["test"]["strategy"]["matrix"]["python"] == ["3.11", "3.12", "3.13", "3.14"]
    assert any(step.get("run") == "npm run check:python" for step in ci["jobs"]["test"]["steps"])
    assert any(step.get("run") == "npm run build" for step in ci["jobs"]["build"]["steps"])
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts["ci"] == "npm run check"
    assert "npm run coverage" in scripts["check:python"]
    assert "npm run check:python" in scripts["check"]
    assert "npm run build" in scripts["check"]
    assert "npm run build:zip" in scripts["build"]
    assert "npm run build:docker" in scripts["build"]


@pytest.mark.skipif(
    os.name == "nt" or not shutil.which("bash") or not shutil.which("git"),
    reason="This GitHub workflow integration test requires POSIX Bash and Git.",
)
def test_badges_workflow_writes_only_separate_branch(tmp_path):
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    environment = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "PYTHONPATH": str(ROOT),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    }

    def git(*args, cwd=source):
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    source.mkdir()
    git("init", "--bare", str(remote), cwd=tmp_path)
    git("init", "-b", "main")
    git(
        "-c",
        "user.name=Test Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Test fixture\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
    )
    git("remote", "add", "origin", str(remote))
    git("push", "origin", "main")
    initial_main = git("rev-parse", "main")
    steps = load_workflow("badges.yml")["jobs"]["update"]["steps"]
    prepare, generate, commit = [step["run"] for step in steps[-3:]]
    previous_badge = None
    for index, python_bytes in enumerate([80, 60, 60]):
        runner_temp = tmp_path / f"runner-{index}"
        runner_temp.mkdir()
        (runner_temp / "languages.json").write_text(
            json.dumps({"Python": python_bytes, "Dockerfile": 100 - python_bytes}), encoding="utf-8"
        )
        env = {**environment, "RUNNER_TEMP": str(runner_temp)}
        for command, cwd in [
            (prepare, source),
            (generate, source),
            (commit, runner_temp / "badges"),
        ]:
            subprocess.run(
                ["bash", "-euo", "pipefail", "-c", command],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
        assert git("--git-dir", str(remote), "rev-parse", "main") == initial_main
        assert git("rev-parse", "HEAD") == initial_main
        assert git("--git-dir", str(remote), "ls-tree", "--name-only", "badges") == "python.json"
        data = json.loads(git("--git-dir", str(remote), "show", "badges:python.json"))
        assert data["message"] == f"{python_bytes:.2f}%"
        badge_commit = git("--git-dir", str(remote), "rev-parse", "badges")
        if index == 2:
            assert badge_commit == previous_badge
        previous_badge = badge_commit
