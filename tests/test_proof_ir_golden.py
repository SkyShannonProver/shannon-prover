"""Byte-identical IR-output golden for build_proof_ir — the characterization net
for the ec_proof_ir split + handles-owner refactor (docs/refactor_ec_proof_ir_blueprint.md).

60 representative fixtures (harvested from test_proof_ir.py's inline current_goal
dicts; 7 layers — ambient_logic / call_site / pr / prhl_module / procedure_body /
procedure_entry / verification_residue) drive build_proof_ir; the canonical IR's
sha256 must match the recorded golden. Any change to the handles flow / pass
output (key reorder, missing key, value drift) surfaces as a hash mismatch — this
is what makes the upcoming _HandlesOwner step (and any future pass-carving)
provably behavior-neutral. No real EasyCrypt: build_proof_ir is a pure function
over parsed goal text. Regenerate intentionally with
tests/fixtures/regen_proof_ir_golden.py.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import _pathsetup  # noqa: F401,E402  (repo root on sys.path)

from core.easycrypt.analysis.ec_proof_ir import build_proof_ir  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "fixtures" / "proof_ir_golden.json").read_text(encoding="utf-8"))


def _canon(ir: dict) -> str:
    return json.dumps(ir, sort_keys=True, default=str)


def test_golden_corpus_is_nonempty_and_multi_layer():
    """Guard: the net must actually exercise the 4 passes, not a degenerate set."""
    assert len(GOLDEN) >= 50
    layers = {build_proof_ir(**e["input"])["current_layer"] for e in GOLDEN}
    assert len(layers) >= 5, layers


def test_golden_corpus_candidate_menu_is_facts_only():
    """The commit's central invariant: candidate_menu surfaces only state-derived
    FACTS, never move GUIDANCE. Re-derived LIVE over the whole corpus (not a sha256,
    not a hand-written table), so a future producer leaking a bare tactic /
    placeholder / route-plan — or a classifier regression — fails HERE with the
    offending item, instead of silently riding a golden regen.

    A surviving menu item must classify `info_kind == "fact"`; the only way a
    hardcoded-noise SHAPE may survive is as a daemon-VERIFIED move (a real provenance
    fact). build_proof_ir runs no daemon, so the corpus carries none — but the guard
    allows it so it stays faithful to `classify_info_kind`.
    """
    from core.easycrypt.analysis.ec_action_contracts import is_hardcoded_noise_move

    surfaced = 0
    leaks = []
    for entry in GOLDEN:
        ir = build_proof_ir(**entry["input"])
        for item in ir.get("candidate_menu") or []:
            if not isinstance(item, dict):
                continue
            surfaced += 1
            info_kind = item.get("info_kind")
            tactic = str(item.get("tactic") or item.get("tactic_shape") or "")
            if info_kind != "fact":
                leaks.append((entry["id"], f"info_kind={info_kind!r}", tactic))
            elif is_hardcoded_noise_move(tactic) and not item.get("verified"):
                leaks.append((entry["id"], "noise-shape-not-verified", tactic))
    assert surfaced >= 100, f"corpus should surface many menu items, got {surfaced} (vacuous?)"
    assert not leaks, f"GUIDANCE/noise leaked into candidate_menu across the golden corpus: {leaks}"


@pytest.mark.parametrize("entry", GOLDEN, ids=[str(e["id"]) for e in GOLDEN])
def test_build_proof_ir_output_byte_identical(entry):
    ir = build_proof_ir(**entry["input"])
    got = hashlib.sha256(_canon(ir).encode("utf-8")).hexdigest()
    assert got == entry["sha256"], (
        f"build_proof_ir IR changed for fixture #{entry['id']} "
        f"(current_layer={ir.get('current_layer')}). The ec_proof_ir split / "
        f"handles-owner refactor MUST be byte-identical. If this change is "
        f"intentional, regenerate tests/fixtures/proof_ir_golden.json."
    )


def test_handles_owner_freeze_enforces_read_only():
    """The _Handles owner makes "PASS 4 is read-only" an ENFORCEABLE invariant
    (the property the future per-pass carving depends on): writes work during the
    mutation phase, a write after freeze() raises, thaw() restores writability for
    downstream consumers, and it serializes identically to a plain dict (so the
    panel-published resources.handles stays byte-identical).
    """
    from core.easycrypt.analysis.ec_proof_ir import _Handles

    h = _Handles({"a": 1})
    h["b"] = 2  # mutation phase (PASS 2/3): OK
    assert dict(h) == {"a": 1, "b": 2}
    assert json.dumps(h, sort_keys=True) == json.dumps({"a": 1, "b": 2}, sort_keys=True)

    h.freeze()
    with pytest.raises(RuntimeError):
        h["c"] = 3  # PASS 4: read-only enforced

    h.thaw()
    h["c"] = 3  # downstream (post-build_proof_ir): writable again
    assert h["c"] == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
