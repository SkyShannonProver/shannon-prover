"""Drive a full proof and capture the panel (followup) the agent sees AT EACH STEP.

For each committed tactic, record the panel the prover would read when DECIDING that
step (the state before the commit), plus the phase and a goal snippet. Used to measure,
step by step, whether the panel's thinness is "nothing to give" or "under-delivered".

Usage: capture_proof_steps.py <file.ec> <lemma> <include_dir> <tactics-json-path> <out-json>
"""
from __future__ import annotations

import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import playground.node_boot as nb

PROFILE = "l4_checked_action_surface"


def _phase_of(view) -> str:
    if not isinstance(view, dict):
        return ""
    ps = view.get("proof_status") or {}
    return f"{ps.get('goal_type','')}/{ps.get('current_layer','')}/{ps.get('view_focus','')}"


def _goal_snippet(view) -> str:
    cg = (view or {}).get("current_goal") if isinstance(view, dict) else None
    lines = (cg or {}).get("lines") if isinstance(cg, dict) else None
    body = "\n".join(str(x) for x in (lines or []))
    # the conclusion region only, trimmed
    return body[-600:]


def main() -> None:
    file, lemma, include_dir, tac_path, out_path = sys.argv[1:6]
    tactics = json.loads(pathlib.Path(tac_path).read_text())
    node = nb.bootstrap_node(file, lemma, PROFILE, include_dir=include_dir)
    turn = node.bootstrap
    steps = []
    for i, tac in enumerate(tactics):
        panel = nb.render_followup(node, turn, PROFILE)
        view = nb.workspace_view_of(turn)
        steps.append({
            "i": i,
            "tactic": tac,
            "phase": _phase_of(view),
            "goal_snippet": _goal_snippet(view),
            "panel": panel,
        })
        sys.stderr.write(f"[{i}] phase={_phase_of(view)[:40]} panel_chars={len(panel)} commit={tac[:40]!r}\n")
        turn = nb.drive(node, json.dumps({"intent": "commit_tactic", "payload": {"tactic": tac}}))
    pathlib.Path(out_path).write_text(json.dumps(steps, indent=2, default=str))
    sys.stderr.write(f"wrote {len(steps)} steps to {out_path}\n")
    nb.dispose(node)


if __name__ == "__main__":
    main()
