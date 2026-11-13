"""The SHANNON_* env registry matches the names the runtime code mentions."""
from __future__ import annotations

import re
from pathlib import Path

from core.env_loader import KNOWN_ENV_FLAGS

_ROOT = Path(__file__).resolve().parents[3]
_CODE_DIRS = ("core", "eval_suite", "experiments", "tools", "workflow")
_NAME = re.compile(r"[\"'](SHANNON_[A-Z0-9_]+)[\"']")


def _mentioned_names() -> set[str]:
    names: set[str] = set()
    for top in _CODE_DIRS:
        for path in (_ROOT / top).rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "env_loader.py":
                continue
            names.update(_NAME.findall(path.read_text(encoding="utf-8")))
    return names


def test_registry_lists_exactly_the_knobs_the_code_mentions() -> None:
    mentioned = _mentioned_names()
    registered = {name for name in KNOWN_ENV_FLAGS if name.startswith("SHANNON_")}
    assert sorted(mentioned - registered) == [], "add these to KNOWN_ENV_FLAGS"
    assert sorted(registered - mentioned) == [], "no code reads these any more"
