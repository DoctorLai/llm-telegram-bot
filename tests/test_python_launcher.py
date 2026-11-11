import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "run-python.cjs"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="npm launcher tests require Node.js.")

HARNESS = r"""
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [], errors = [], signals = [];
const state = {
  argv: ['node', 'run-python.cjs', ...input.args],
  env: input.env || {},
  platform: input.platform || 'linux',
  pid: 123,
  exitCode: 0,
  kill: (pid, signal) => signals.push({ pid, signal }),
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  __dirname: '/project with spaces/scripts',
  process: state,
  console: { error: message => errors.push(message) },
  require: name => {
    if (name === 'node:path') return path.posix;
    if (name === 'node:fs') return { existsSync: () => input.hasVenv || false };
    if (name === 'node:child_process') return {
      spawnSync: (executable, args, options) => {
        calls.push({ executable, args, options });
        return input.results[calls.length - 1];
      },
    };
    throw new Error(`Unexpected dependency: ${name}`);
  },
});
console.log(JSON.stringify({ calls, errors, signals, status: state.exitCode }));
"""


def simulate(**settings):
    settings.setdefault("args", ["-m", "pytest", "-k", "two words; literal"])
    settings.setdefault("results", [{"status": 0}])
    result = subprocess.run(
        [NODE, "-e", HARNESS, str(LAUNCHER)],
        input=json.dumps(settings),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"hasVenv": True}, "/project with spaces/.venv/bin/python"),
        ({"hasVenv": True, "platform": "win32"}, "/project with spaces/.venv/Scripts/python.exe"),
        ({"hasVenv": True, "env": {"VIRTUAL_ENV": "/active env"}}, "/active env/bin/python"),
        ({"env": {"VIRTUAL_ENV": "/active"}, "platform": "win32"}, "/active/Scripts/python.exe"),
        ({}, "python3"),
    ],
)
def test_selects_python_and_passes_arguments_without_a_shell(settings, expected):
    result = simulate(**settings)
    assert result["status"] == 0
    assert result["errors"] == []
    assert result["calls"] == [
        {
            "executable": expected,
            "args": ["-m", "pytest", "-k", "two words; literal"],
            "options": {"stdio": "inherit"},
        }
    ]


def test_falls_back_to_python_only_when_python3_does_not_exist():
    result = simulate(results=[{"error": {"code": "ENOENT"}}, {"status": 0}])
    assert [call["executable"] for call in result["calls"]] == ["python3", "python"]
    assert result["status"] == 0


@pytest.mark.parametrize("status", [1, 2, 5])
def test_child_failures_are_preserved_without_retrying_another_interpreter(status):
    result = simulate(results=[{"status": status}])
    assert result["status"] == status
    assert len(result["calls"]) == 1


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        ({"hasVenv": True}, "ENOENT"),
        ({"env": {"VIRTUAL_ENV": "/broken"}}, "ENOENT"),
        ({}, "EACCES"),
    ],
)
def test_broken_selected_environments_fail_visibly(settings, code):
    result = simulate(**settings, results=[{"error": {"code": code, "message": "test failure"}}])
    assert result["status"] == 1
    assert len(result["calls"]) == 1
    assert "Cannot start" in result["errors"][0]


def test_missing_python_has_setup_guidance():
    result = simulate(results=[{"error": {"code": "ENOENT"}}] * 2)
    assert result["status"] == 1
    assert "Python 3.11+" in result["errors"][0]
    assert "requirements-dev.txt" in result["errors"][0]


def test_signal_termination_is_forwarded():
    result = simulate(results=[{"status": None, "signal": "SIGTERM"}])
    assert result["signals"] == [{"pid": 123, "signal": "SIGTERM"}]
    assert len(result["calls"]) == 1


@pytest.mark.skipif(os.name == "nt", reason="This test creates POSIX interpreter symlinks.")
@pytest.mark.parametrize("use_venv", [True, False])
def test_real_launcher_works_without_a_python_command_on_path(tmp_path, use_venv):
    project = tmp_path / "project with spaces"
    script = project / "scripts" / LAUNCHER.name
    script.parent.mkdir(parents=True)
    shutil.copyfile(LAUNCHER, script)
    interpreter = project / (".venv/bin/python" if use_venv else "bin/python3")
    interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to(sys.executable)
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    environment["PATH"] = "" if use_venv else str(interpreter.parent)
    result = subprocess.run(
        [
            NODE,
            str(script),
            "-c",
            "import sys; print(sys.argv[1])",
            "literal argument; with spaces",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout.strip() == "literal argument; with spaces"


def test_all_python_npm_commands_use_the_launcher():
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    for name in (
        "start",
        "config:check",
        "format",
        "format:check",
        "lint",
        "test",
        "coverage",
        "build:zip",
    ):
        assert all(
            command.startswith("node scripts/run-python.cjs ")
            for command in scripts[name].split(" && ")
        ), name
