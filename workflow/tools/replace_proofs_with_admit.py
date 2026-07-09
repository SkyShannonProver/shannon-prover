"""CLI: replace every proved lemma/equiv/hoare proof body with admit.

The transform now lives in ``core/easycrypt/proof_strip.py`` (the lower layer)
so ``core`` can use it without importing ``workflow`` — this module is the CLI
shim + back-compat re-export.

Usage:
    python3 -m workflow.tools.replace_proofs_with_admit <path.ec> [<path2.ec> ...]
"""

import sys
from pathlib import Path

from core.easycrypt.proof_strip import (  # noqa: F401  (re-exported for callers)
    _is_admit_only_proof,
    _make_admit_block,
    _redact_residual_proof_text,
    replace_proofs,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: replace_proofs_with_admit.py <path.ec> [<path2.ec> ...]", file=sys.stderr)
        sys.exit(2)
    for arg in sys.argv[1:]:
        path = Path(arg)
        original = path.read_text(encoding="utf-8")
        new, n = replace_proofs(original)
        path.write_text(new, encoding="utf-8")
        print(f"{path}: replaced {n} proof(s)")


if __name__ == "__main__":
    main()
