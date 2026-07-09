"""Deterministic OLD-vs-NEW diff of the changed panel producers across all 89 items.

For each item, recompute the producers the 7 fix commits touched (goal-text based:
goal_operators, goal_head_operators, opener reduce_with, tactic_forms gating) and
compare to the OLD followup the audit captured. Emits one JSON record per item that
CHANGED, for the adversarial verification workflow to judge.
"""
from __future__ import annotations

import json
import re
import sys
import pathlib
import glob

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import workflow.surface_profiles as SP

DIR = pathlib.Path(__file__).resolve().parent / "items"


def _view(goal: str) -> dict:
    return {"current_goal": {"lines": goal.splitlines()},
            "facts_and_diagnostics": {"facts": {}}}


def _old_goal_operators(fu: str) -> list[str]:
    out, grab = [], False
    for ln in fu.splitlines():
        if "Goal operators" in ln:
            grab = True
            continue
        if grab:
            m = re.match(r"\s*-\s*`([^`]+)`\s*$", ln)
            if m:
                out.append(m.group(1))
            elif ln.strip() and not ln.strip().startswith("-"):
                break
    return out


def _two_sided(goal: str) -> bool:
    # relational goal (two programs / &1&2) -> two-sided; single phoare/hoare -> one-sided
    return ("&1" in goal and "&2" in goal) or "~" in goal


def main() -> None:
    records = []
    for p in sorted(glob.glob(str(DIR / "item_*.json")),
                    key=lambda x: int(re.findall(r"\d+", x)[-1])):
        d = json.load(open(p))
        i = int(re.findall(r"\d+", p)[-1])
        goal, fu, phase = d["goal"], d["followup"], d["phase"]
        view = _view(goal)
        changed = {}

        # ② goal_operators (type/binder dump) — only where the panel surfaces it
        if "Goal operators" in fu:
            old = _old_goal_operators(fu)
            try:
                from workflow.proof_management.analyzers.pure_tail import _goal_operators
                new = _goal_operators(goal)
            except Exception:
                new = None
            if new is not None and old != new:
                changed["goal_operators"] = {"old": old, "new": new,
                                             "removed": [o for o in old if o not in new],
                                             "added": [n for n in new if n not in old]}

        # ② head-operator routing (+^ vs ^)
        ho = SP._goal_head_operators(view)
        if "operator=\"(^)\"" in fu.replace(" ", "") or "(^)" in fu:
            if "(+^)" in ho and "(^)" not in ho:
                changed["operator_route"] = {"new_head_ops": ho, "note": "rerouted (^)->(+^)"}

        # ③ opener reduce_with
        if phase == "opener":
            new_rw = SP._render_opener_focus(view).get("reduce_with") or []
            old_rw = [ln.strip().lstrip("- ") for ln in fu.splitlines()
                      if ln.strip().startswith("- `") and ("byequiv" in ln or "byphoare" in ln
                                                            or "ler_trans" in ln or "rewrite" in ln)]
            if [r[:40] for r in new_rw] != [r[:40] for r in old_rw]:
                changed["opener_reduce"] = {"old": old_rw, "new": new_rw}

        # ⑤ tactic_forms gating
        from core.easycrypt.session_prover_workspace_view import _prhl_surgery_tactic_handles
        ts = _two_sided(goal)
        new_forms = sorted(n for n in
                           {(h.get("payload") or {}).get("name")
                            for h in _prhl_surgery_tactic_handles(ts, goal_text=goal)} if n)
        full_forms = sorted(n for n in
                            {(h.get("payload") or {}).get("name")
                             for h in _prhl_surgery_tactic_handles(ts)} if n)
        dropped = [f for f in full_forms if f not in new_forms]
        if dropped and ("tactic_forms" in fu):
            changed["tactic_forms_gated"] = {"dropped": dropped, "kept": new_forms}

        if changed:
            records.append({"i": i, "id": d["id"], "phase": phase,
                            "goal_head": "\n".join(goal.splitlines()[:40]),
                            "next_tactics": d["next_tactics"][:3],
                            "changed": changed})
    json.dump(records, open(DIR.parent / "rerender_records.json", "w"), indent=2, default=str)
    # summary
    from collections import Counter
    c = Counter()
    for r in records:
        for k in r["changed"]:
            c[k] += 1
    print(f"items changed: {len(records)} / 89")
    for k, v in c.items():
        print(f"  {k}: {v} items")


if __name__ == "__main__":
    main()
