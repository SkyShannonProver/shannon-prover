"""Re-capture the RAW program_frontier / frontier_alignment for an audited frontier.

Bootstraps a lemma, replays a committed prefix, and dumps the analyzer's raw
output (frontier_alignment.rows + first_instruction_alignment, and the proof_ir
structured_regions when reachable) so FIX-B2/B3 can be grounded in real data.

Usage:
    capture_frontier.py <file.ec> <lemma> <include_dir> '<prefix-json-list>'
"""
from __future__ import annotations

import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root on sys.path

import playground.node_boot as nb


def _turn_error(turn) -> str:
    """Best-effort: surface a backend error/rejection from a ManagedTurn."""
    for attr in ("error", "rejection", "failure"):
        v = getattr(turn, attr, None)
        if v:
            return str(v)
    wv = nb.workspace_view_of(turn)
    st = wv.get("proof_status") if isinstance(wv, dict) else None
    if isinstance(st, dict) and st.get("last_error"):
        return str(st.get("last_error"))
    return ""


def main() -> None:
    file, lemma, include_dir, prefix_json = sys.argv[1:5]
    prefix = json.loads(prefix_json)
    node = nb.bootstrap_node(
        file, lemma, "l4_checked_action_surface", include_dir=include_dir
    )
    turn = node.bootstrap
    for i, tac in enumerate(prefix):
        intent = json.dumps({"intent": "commit_tactic", "payload": {"tactic": tac}})
        turn = nb.drive(node, intent)
        err = _turn_error(turn)
        sys.stderr.write(f"[{i}] commit {tac[:50]!r} -> err={err or 'ok'}\n")
    view = nb.workspace_view_of(turn)
    pf = view.get("program_frontier") if isinstance(view, dict) else None
    cg = view.get("current_goal") if isinstance(view, dict) else None
    # The proof_ir structured_regions feed the alignment analyzer (region undercount lives
    # there); reach them through the manager's latest full view / proof_ir if exposed.
    full = getattr(node.manager, "latest_full_view", None)
    proof_ir = None
    if isinstance(full, dict):
        proof_ir = (((full.get("resources") or {}).get("handles") or {})
                    .get("procedure_body_frontend"))
    out = {
        "lemma": lemma,
        "current_goal_lines": (cg or {}).get("lines") if isinstance(cg, dict) else None,
        "program_frontier": pf,
        "structured_regions": (proof_ir or {}).get("structured_regions") if isinstance(proof_ir, dict) else None,
    }
    print(json.dumps(out, indent=2, default=str))
    nb.dispose(node)


if __name__ == "__main__":
    main()
