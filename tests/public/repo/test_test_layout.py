"""Keep the test tree classified.

A test lives at ``tests/public/<area>/`` or ``tests/private/<area>/``. The
export ships ``tests/public/`` (plus ``tests/helpers/`` and ``conftest.py``)
and keeps every other path under ``tests/`` private, so where a test is placed
decides whether it is published. Shared code belongs in ``tests/helpers/``.
The public tree has no ``tests/private/``; these checks then cover only the
public part.
"""

import re
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[2]

PUBLIC_AREAS = {"core", "compiler", "workflow", "eval", "interleaved", "repo"}
PRIVATE_AREAS = {"research", "cmac", "release"}
_TOP_LEVEL = {"conftest.py"}


def _python_files():
    return sorted(p for p in _TESTS.rglob("*.py") if "__pycache__" not in p.parts)


def test_every_test_module_sits_in_a_known_area():
    misplaced = []
    for path in _python_files():
        rel = path.relative_to(_TESTS)
        parts = rel.parts
        if len(parts) == 1:
            if parts[0] not in _TOP_LEVEL:
                misplaced.append(f"{rel} (top-level: move it into an area or helpers/)")
            continue
        if parts[0] == "helpers":
            if path.name.startswith("test_"):
                misplaced.append(f"{rel} (a test module inside helpers/)")
            continue
        areas = {"public": PUBLIC_AREAS, "private": PRIVATE_AREAS}.get(parts[0])
        if areas is None:
            misplaced.append(f"{rel} (unknown top-level directory {parts[0]}/)")
        elif parts[1] == "fixtures":
            continue
        elif len(parts) != 3 or parts[1] not in areas:
            misplaced.append(f"{rel} (expected tests/{parts[0]}/<{'|'.join(sorted(areas))}>/)")
        elif not path.name.startswith("test_"):
            misplaced.append(f"{rel} (shared code belongs in tests/helpers/)")
    assert not misplaced, "misplaced test files:\n  " + "\n  ".join(misplaced)


def test_test_module_basenames_are_unique():
    """pytest's default import mode imports a test module by its basename."""
    seen: dict[str, Path] = {}
    duplicates = []
    for path in _python_files():
        if not path.name.startswith("test_"):
            continue
        if path.name in seen:
            duplicates.append(f"{seen[path.name].relative_to(_TESTS)} and {path.relative_to(_TESTS)}")
        seen.setdefault(path.name, path)
    assert not duplicates, "duplicate test module names: " + "; ".join(duplicates)


def test_public_tests_do_not_depend_on_private_tests():
    reference = re.compile(r"tests[./]private\b")
    offenders = []
    for root in (_TESTS / "public", _TESTS / "helpers"):
        for path in sorted(root.rglob("*")):
            if path == Path(__file__).resolve():
                continue
            if path.is_file() and path.suffix in {".py", ".json", ".ec"}:
                if reference.search(path.read_text(encoding="utf-8", errors="replace")):
                    offenders.append(str(path.relative_to(_TESTS)))
    for name in _TOP_LEVEL:
        if reference.search((_TESTS / name).read_text(encoding="utf-8")):
            offenders.append(name)
    assert not offenders, "public test files reference tests/private: " + ", ".join(offenders)
