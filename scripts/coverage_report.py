"""Run coverage and enforce an unrounded 80% floor for every reported metric."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

THRESHOLD = 80
REPORT_PATH = Path("coverage-report.json")
COVERAGE_PATH = Path("coverage.json")


def metrics(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Count executable lines, statements, entered functions, and taken branches."""
    totals = data["totals"]
    functions = [
        function
        for file in data["files"].values()
        for name, function in file["functions"].items()
        if name and function["summary"]["num_statements"]
    ]
    return {
        "Lines": {"covered": totals["covered_lines"], "total": totals["num_statements"]},
        "Statements": {"covered": totals["covered_lines"], "total": totals["num_statements"]},
        "Functions": {
            "covered": sum(function["summary"]["covered_lines"] > 0 for function in functions),
            "total": len(functions),
        },
        "Branches": {"covered": totals["covered_branches"], "total": totals["num_branches"]},
    }


def percentage(metric: dict[str, int]) -> float:
    """Treat metrics with no executable items as fully covered."""
    return 100 * metric["covered"] / metric["total"] if metric["total"] else 100.0


def write_report(data: dict[str, Any], path: Path = REPORT_PATH) -> bool:
    """Save machine-readable summary and per-file counts; return whether all gates pass."""
    summary = metrics(data)
    if not summary["Lines"]["total"]:
        raise ValueError("Coverage contains no executable statements.")
    report = {
        "threshold": THRESHOLD,
        "metrics": summary,
        "files": [
            {
                "name": name,
                "covered": file["summary"]["covered_lines"],
                "total": file["summary"]["num_statements"],
                "branches_covered": file["summary"]["covered_branches"],
                "branches_total": file["summary"]["num_branches"],
            }
            for name, file in sorted(data["files"].items())
        ],
    }
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for category, metric in summary.items():
        print(
            f"{category}: {percentage(metric):.2f}% (minimum {THRESHOLD}%) "
            f"{metric['covered']} / {metric['total']}"
        )
    return all(percentage(metric) >= THRESHOLD for metric in summary.values())


def main() -> int:
    """Run pytest, always report available coverage, and preserve test failures."""
    COVERAGE_PATH.unlink(missing_ok=True)
    REPORT_PATH.unlink(missing_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov",
            "--cov-report=term-missing",
            "--cov-report=json",
            "--cov-report=xml",
            "--cov-report=html",
        ],
        check=False,
    )
    if not COVERAGE_PATH.is_file():
        print("Coverage data was not produced.", file=sys.stderr)
        return result.returncode or 1
    data = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    passed = write_report(data)
    return result.returncode or (0 if passed else 1)


if __name__ == "__main__":
    raise SystemExit(main())
