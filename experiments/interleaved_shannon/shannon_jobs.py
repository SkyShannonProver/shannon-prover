#!/usr/bin/env python3
"""Compatibility entry for the ChaChaPoly reference protocol."""

import sys
from pathlib import Path

_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_ROOT))

from experiments.interleaved_shannon.reference import reference_context
from workflow.interleaved import jobs


def main(argv: list[str] | None = None) -> int:
    return jobs.main(argv, context=reference_context())


if __name__ == "__main__":
    raise SystemExit(main())
