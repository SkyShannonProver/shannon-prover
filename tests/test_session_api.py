"""Pure-Python tests for the public EasyCrypt session facade."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.session_api import open_session  # type: ignore  # noqa: E402
from core.easycrypt import session_api as package_session_api  # noqa: E402


def test_open_session_facade() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = open_session(Path(td))
        assert session.dir == Path(td)
        assert session.curr.exists()


def test_package_import_boundary() -> None:
    with tempfile.TemporaryDirectory() as td:
        session = package_session_api.open_session(Path(td))
        assert session.dir == Path(td)


if __name__ == "__main__":
    test_open_session_facade()
    test_package_import_boundary()
    print("PASS test_session_api")
