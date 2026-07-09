"""Public session facade for EasyCrypt tooling.

``session_runtime.py`` owns the concrete ``Session`` implementation. Non-CLI
modules should import this facade instead of importing the runtime module
directly, so the public boundary stays small.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def session_class() -> type:
    """Return the concrete session class without exposing its module path."""
    from core.easycrypt.session_runtime import Session  # type: ignore
    return Session


def open_session(
    session_dir: Path | str,
    include_dirs: list[str] | None = None,
) -> Any:
    """Open an EasyCrypt proof session."""
    return session_class()(Path(session_dir), include_dirs=include_dirs)


def explain_no_progress(tactic: str, goal_raw: str) -> str:
    """Return context-specific no-progress advice for a tactic."""
    from core.easycrypt.session_diagnostics import explain_no_progress as _explain  # type: ignore
    return _explain(tactic, goal_raw)
