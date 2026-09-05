#!/usr/bin/env python3
"""Compatibility entry for the ChaChaPoly reference protocol."""

import sys
from pathlib import Path

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from experiments.interleaved_shannon._compat import bind_reference_project

bind_reference_project()

from workflow.interleaved import inner_runner as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
