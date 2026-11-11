"""Generate a Shields endpoint from GitHub Linguist's repository byte counts."""

import argparse
import json
from pathlib import Path


def language_badge(languages: dict[str, int]) -> dict[str, str | int]:
    """Report the Python share; reject malformed API responses instead of hiding errors."""
    if not languages or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in languages.values()
    ):
        raise ValueError("Expected nonnegative GitHub language byte counts.")
    total = sum(languages.values())
    if total == 0:
        raise ValueError("GitHub reported no source bytes.")
    return {
        "schemaVersion": 1,
        "label": "Python",
        "message": f"{100 * languages.get('Python', 0) / total:.2f}%",
        "color": "3776ab",
        "namedLogo": "python",
    }


def main() -> None:
    """Read GitHub's languages JSON and write a badge into the separate badges checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    languages = json.loads(args.input.read_text(encoding="utf-8"))
    badge = language_badge(languages)
    args.output.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
