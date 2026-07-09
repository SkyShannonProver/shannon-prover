# Panel-quality audit harness

Reproducible harness for the Shannon Prover **panel-quality** program: capture the exact
`followup` panel the prover reads at any frontier, and audit/measure it. See the full handoff
brief for motivation and methodology; this README is the runnable index.

## What's here
- `capture_frontier.py` — bootstrap a lemma, replay a committed prefix (a JSON list of tactic
  lines), and dump the RAW `program_frontier` (the analyzer's rows/location/first_instruction_
  alignment). Use to ground call-frontier / setup-count findings against real analyzer output.
  `capture_frontier.py <file.ec> <lemma> <include_dir> '<prefix-json-list>'`
- `capture_proof_steps.py` — drive a FULL proof and dump, per step, the panel the agent sees +
  phase + goal snippet. Feed it the proof's tactic lines (extract from the lemma's `.ec` body,
  between `proof.` and `qed.`, one tactic per non-comment line).
  `capture_proof_steps.py <file.ec> <lemma> <include_dir> <tactics.json> <out.json>`
- `rerender_diff.py` — recompute the changed goal-text producers (goal_operators / head-operator
  routing / opener reduce_with / tactic_forms gating) across a captured corpus and emit the
  OLD-vs-NEW diff per item, for the adversarial verify workflow.
- `workflows/three_agent_panel_audit.js` — the 3-agent adversarial audit (demand → supply →
  verify → synthesis) over a corpus of `item_<i>.json` frontiers. **This is the canonical
  panel audit.**
- `workflows/per_lemma_perstep_measure.js` — per-step "nothing-to-give vs under-delivered"
  classifier over one lemma's captured steps (the PIR_correct measurement).
- `workflows/rerender_diff_verify.js` — adversarial per-item judge of the OLD-vs-NEW producer
  diff (improvement / neutral / regression).

## Run prerequisites
- opam EasyCrypt switch: `eval "$(opam env --switch=easycrypt)"`, and run **without an OS
  sandbox** (why3 needs the `nice()` syscall). Drive with `uv run python ...`.
- `node_boot` (`playground/node_boot.py`) must import — the scripts add the repo root to
  `sys.path` via `parents[1]`, which assumes this dir is **under tools/ (paths resolve two levels up to the repo root)**.

## ⚠️ Machine-specific paths (adjust before running)
These scripts were authored against a specific checkout and a gitignored corpus dir, so they
carry hardcoded absolute paths and a corpus that does NOT travel with git:
- The corpus `item_<i>.json` (89 frontiers) and the per-lemma `*_steps.json` live in
  `.panel_audit_handoff/` (gitignored — NOT pushed). **Regenerate
  the public ones** with `capture_proof_steps.py` / `capture_frontier.py` on tier-A `.ec` files
  (e.g. `eval/examples/PIR.ec` · `PIR_correct`), or sync the dir out-of-band.
- `workflows/*.js` and `rerender_diff.py` hardcode an absolute `DIR = .../.panel_audit_handoff/...`
  and pass item indices as `args`. Repoint `DIR` to your corpus before running. The workflow
  `args` is the integer count / index list.

## The three roles (audit), in one line each
1. DEMAND — sees goal + committed next tactics, NOT the panel; writes the ranked mechanical
   help a tool could supply (`c_needs` = the yardstick).
2. SUPPLY — sees goal + the live panel + #1's demand; grades each element super有用 / necessary
   / 鸡肋 / 误导, re-deriving every structural claim FROM THE GOAL.
3. VERIFY — sees only #2's 误导 flags; re-derives the goal and tries to REFUTE each (defaults to
   refute). Only #3-confirmed 误导 count.
