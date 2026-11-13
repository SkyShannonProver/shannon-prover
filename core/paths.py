"""The repository root, for modules imported from inside the package tree.

Entry points that put the root on ``sys.path`` before ``core`` is importable
keep their own ``Path(__file__)`` computation.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
