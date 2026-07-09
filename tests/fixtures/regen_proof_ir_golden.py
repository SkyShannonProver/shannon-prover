"""Regenerate tests/fixtures/proof_ir_golden.json — the build_proof_ir IR golden.

Run ONLY when a build_proof_ir behavior change is intentional (the golden test
test_proof_ir_golden.py will otherwise flag it). Harvests the literal
current_goal-kwarg build_proof_ir(...) calls from tests/test_proof_ir.py and
records the sha256 of each canonical IR.

    python tests/fixtures/regen_proof_ir_golden.py
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402


def _canon(ir: dict) -> str:
    return json.dumps(ir, sort_keys=True, default=str)


def main() -> None:
    src = (ROOT / "tests" / "test_proof_ir.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fixtures, seen = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "build_proof_ir":
                continue
            kw, ok = {}, True
            for k in node.keywords:
                try:
                    kw[k.arg] = ast.literal_eval(k.value)
                except Exception:
                    ok = False
                    break
            if ok and "current_goal" in kw:
                key = json.dumps(kw, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    fixtures.append(kw)

    golden = []
    for i, kw in enumerate(sorted(fixtures, key=lambda k: json.dumps(k, sort_keys=True, default=str))):
        ir = build_proof_ir(**kw)
        golden.append({"id": i, "input": kw,
                       "sha256": hashlib.sha256(_canon(ir).encode("utf-8")).hexdigest()})

    out = ROOT / "tests" / "fixtures" / "proof_ir_golden.json"
    out.write_text(json.dumps(golden, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} — {len(golden)} fixtures")


if __name__ == "__main__":
    main()
