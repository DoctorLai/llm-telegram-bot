import json
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scripts import coverage_report, language_badge


@pytest.fixture
def coverage_data():
    summary = {
        "covered_lines": 80,
        "num_statements": 100,
        "covered_branches": 8,
        "num_branches": 10,
    }
    return {
        "totals": summary,
        "files": {
            "bot.py": {
                "summary": summary,
                "functions": {
                    "": {"summary": {"covered_lines": 20, "num_statements": 20}},
                    "called": {"summary": {"covered_lines": 4, "num_statements": 5}},
                    "also_called": {"summary": {"covered_lines": 4, "num_statements": 5}},
                    "third": {"summary": {"covered_lines": 4, "num_statements": 5}},
                    "fourth": {"summary": {"covered_lines": 4, "num_statements": 5}},
                    "not_called": {"summary": {"covered_lines": 0, "num_statements": 5}},
                    "excluded": {"summary": {"covered_lines": 0, "num_statements": 0}},
                },
            }
        },
    }


def test_report_counts_executable_metrics_and_file_coverage(coverage_data, tmp_path):
    output = tmp_path / "report.json"
    original = deepcopy(coverage_data)
    assert coverage_report.write_report(coverage_data, output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["threshold"] == 80
    assert report["metrics"] == {
        "Lines": {"covered": 80, "total": 100},
        "Statements": {"covered": 80, "total": 100},
        "Functions": {"covered": 4, "total": 5},
        "Branches": {"covered": 8, "total": 10},
    }
    assert report["files"] == [
        {"name": "bot.py", "covered": 80, "total": 100, "branches_covered": 8, "branches_total": 10}
    ]
    assert coverage_data == original


@pytest.mark.parametrize("metric", ["lines", "branches", "functions"])
def test_each_metric_enforces_the_floor(coverage_data, tmp_path, metric):
    if metric == "lines":
        coverage_data["totals"]["covered_lines"] = 79
    elif metric == "branches":
        coverage_data["totals"]["covered_branches"] = 7
    else:
        coverage_data["files"]["bot.py"]["functions"]["called"]["summary"]["covered_lines"] = 0
    assert not coverage_report.write_report(coverage_data, tmp_path / "report.json")


def test_rounding_cannot_turn_a_failure_into_success(coverage_data, tmp_path):
    coverage_data["totals"].update(covered_lines=79999, num_statements=100000)
    assert not coverage_report.write_report(coverage_data, tmp_path / "report.json")
    assert coverage_report.percentage({"covered": 0, "total": 0}) == 100


def test_empty_coverage_fails(coverage_data, tmp_path):
    coverage_data["totals"]["num_statements"] = 0
    with pytest.raises(ValueError, match="no executable statements"):
        coverage_report.write_report(coverage_data, tmp_path / "report.json")


@pytest.mark.parametrize(("exit_code", "covered", "expected"), [(0, 80, 0), (1, 80, 1), (0, 79, 1)])
def test_coverage_command_preserves_test_and_threshold_failures(
    coverage_data, tmp_path, monkeypatch, exit_code, covered, expected
):
    monkeypatch.chdir(tmp_path)
    coverage_report.COVERAGE_PATH.write_text("stale data", encoding="utf-8")
    coverage_report.REPORT_PATH.write_text("stale report", encoding="utf-8")
    coverage_data["totals"]["covered_lines"] = covered

    def run(command, check):
        assert command[:3] == [sys.executable, "-m", "pytest"]
        assert "--cov-report=html" in command
        assert check is False
        assert not coverage_report.COVERAGE_PATH.exists()
        assert not coverage_report.REPORT_PATH.exists()
        coverage_report.COVERAGE_PATH.write_text(json.dumps(coverage_data), encoding="utf-8")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(coverage_report.subprocess, "run", run)
    assert coverage_report.main() == expected
    assert coverage_report.REPORT_PATH.is_file()


@pytest.mark.parametrize("code", [0, 2])
def test_missing_coverage_is_a_failure(tmp_path, monkeypatch, capsys, code):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        coverage_report.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=code)
    )
    assert coverage_report.main() == (code or 1)
    assert "not produced" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("languages", "expected"),
    [
        ({"Python": 80, "Dockerfile": 20}, "80.00%"),
        ({"Python": 5}, "100.00%"),
        ({"Go": 1}, "0.00%"),
    ],
)
def test_language_badge_uses_repository_byte_counts(languages, expected):
    badge = language_badge.language_badge(languages)
    assert badge["schemaVersion"] == 1
    assert badge["message"] == expected
    assert badge["label"] == "Python"


@pytest.mark.parametrize(
    "data", [{}, {"Python": 0}, {"Python": -1}, {"Python": True}, {"error": "bad"}]
)
def test_bad_language_data_is_not_a_success_badge(data):
    with pytest.raises(ValueError):
        language_badge.language_badge(data)


def test_language_badge_command(tmp_path, monkeypatch):
    source = tmp_path / "languages.json"
    output = tmp_path / "python.json"
    source.write_text('{"Python": 99, "Dockerfile": 1}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["language_badge", str(source), str(output)])
    language_badge.main()
    assert json.loads(output.read_text(encoding="utf-8"))["message"] == "99.00%"
