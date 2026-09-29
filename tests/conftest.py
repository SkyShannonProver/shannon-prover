"""Pytest auto-loaded config for the tests/ tree.

Ensures the project root is on ``sys.path`` so pytest-style test
files can ``from workflow.agents import prover`` etc. without each
test file having to repeat the path-setup boilerplate.

Standalone test scripts (``python3 tests/test_foo.py``) typically do
their own ``sys.path.insert(0, ROOT)`` — this conftest only matters
when pytest is the runner.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
