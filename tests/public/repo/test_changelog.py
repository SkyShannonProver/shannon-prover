"""CHANGELOG.md keeps one shape, so union merges of parallel entries stay readable.

.gitattributes merges the changelog with `merge=union`: two branches that both
add entries keep both instead of conflicting. A union merge can also duplicate
a line or splice a heading, which these checks catch.
"""
import re
from pathlib import Path

_CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"
_VERSION = re.compile(r"^## (\d+)\.(\d+)\.(\d+) \((\d{4}-\d{2}-\d{2})\)$")
_DATED = re.compile(r"^## (\d{4}-\d{2}-\d{2})( – \d{4}-\d{2}-\d{2})?$")


def _headings() -> list[str]:
    return [line for line in _CHANGELOG.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")]


def test_headings_are_unreleased_then_versions_then_dates_newest_first():
    headings = _headings()
    if headings and headings[0] == "## Unreleased":
        headings = headings[1:]
    assert "## Unreleased" not in headings, "only one Unreleased section, at the top"
    versions = [h for h in headings if _VERSION.match(h)]
    dated = [h for h in headings if _DATED.match(h)]
    assert headings == versions + dated, (
        "every heading is `## X.Y.Z (date)` or `## date`, versions before dates: "
        + str([h for h in headings if h not in versions + dated]))
    keys = [tuple(int(x) for x in _VERSION.match(h).groups()[:3]) for h in versions]
    assert keys == sorted(keys, reverse=True), "versions newest first"
    dates = [_DATED.match(h).group(1) for h in dated]
    assert dates == sorted(dates, reverse=True), "dated sections newest first"


def test_no_entry_appears_twice():
    lines = [line for line in _CHANGELOG.read_text(encoding="utf-8").splitlines()
             if line.startswith("- ")]
    seen, duplicates = set(), []
    for line in lines:
        if line in seen:
            duplicates.append(line)
        seen.add(line)
    assert not duplicates, f"duplicated changelog entries: {duplicates[:5]}"
