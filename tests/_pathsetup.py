"""Single home for the test-file path bootstrap.

Direct script runs (``python tests/test_x.py``) put ``tests/`` on sys.path,
so ``import _pathsetup`` resolves and inserts the repo root; under pytest the
same import resolves via rootdir/prepend semantics (conftest.py has already
inserted the root by then — this is a no-op there). Replaces the per-file
``ROOT = ...; sys.path.insert(...)`` boilerplate that had drifted or rotted
in over a hundred files.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
