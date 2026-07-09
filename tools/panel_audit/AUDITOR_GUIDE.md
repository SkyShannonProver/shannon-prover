# Panel-Audit Artifact Guide (for auditor agents)

## What this is

We took **real recorded agent runs** (`agent_view_runs/<lemma>/<run>/`) and
**deterministically replayed the exact agent action script** (the
`handled_intent` stream: probe / commit / inspect / lookup / undo) through a
**fresh ProofNodeManager built from the CURRENT mcp-v0 checkout**. No live LLM
was in the loop — the moves are fixed, from the bundle. For every turn we
captured, side by side:

- the **genuine raw EasyCrypt output** (ground truth), and
- the **current-code agent-facing panel** (the "inline read") + full view JSON.

Your job: **compare the current-code panel against the raw EC ground truth** and
report where the panel **loses information, diverges from EC, mislabels, or
hallucinates**. You are auditing the CURRENT code's panels — the recorded run is
only the source of the action script (and a "what the agent saw then" reference).

## Layout

```
artifacts/panel_audit/<run>/
  audit_index.json          # per-turn summary: intent, ok, goal_hash, n_backend_calls, rc
  bootstrap_current_view.json
  steps/turn_NNN/
    intent.json             # the agent move replayed this turn
    raw_ec.txt              # GROUND TRUTH: raw session_cli stdout/stderr for this turn's
                            #   backend calls. For probes: the `[TRY]` block incl
                            #   `goal_after_raw`. For commits: `-next` output. For
                            #   inspect/lookup: `-goal-info`/`-where`/... raw stdout.
                            #   Also includes the raw `-agent-view` JSON dump.
    raw_ec_actions.json     # structured: [{label,args,returncode,raw_stdout,raw_stderr}]
    current_view.json       # CURRENT-code agent-facing ProverWorkspaceView (ALL panels:
                            #   current_goal, proof_status, candidate_moves,
                            #   program_frontier, call_site_surface, application_context,
                            #   facts_and_diagnostics, inspect_lookup_handles)
    current_panel.md        # CURRENT-code inline read (L4 render) the prover would see
    current_panel_l1.md     # SAME EC state rendered at the L1 goal-only baseline
    snapshot.json           # goal_hash, goal_type, goal_lines (current code)
    manager_actions.json    # manager action summaries (parsed observation, error_summary)
    recorded_view.json      # what the bundle captured at run time (reference)
    recorded_panel.md       # the inline read the agent ACTUALLY saw then (reference)
```

## Runs available (goal-type coverage)

| run | lemma | goal type | profile | turns |
|---|---|---|---|---|
| `mee_decrypt_correct/Tree_0_0` | mee_decrypt_correct | phoare / procedure | L4 | 15 |
| `equiv_fwhile_L4` | equiv_fwhile_fiwhile | equiv / pRHL / while | L4 | 8 |
| `pr_G4_L4` | pr_G4 | phoare / pr (cramer-shoup) | L4 | 29 |
| `pr_distinguish_L4` | pr_distinguish_simul_from_three_perm | pr (private held-out corpus) | L4 | 4 |
| `pr_distinguish_L1` | pr_distinguish_simul_from_three_perm | pr (private held-out corpus) | L1 (real L1 run) | ~11 |

## Ground-truth reading tips

- The raw EC goal for a **probe** is in `raw_ec.txt` under
  `[TRY] goal_after_raw:` (and structurally in the `candidate_after` block of the
  `-agent-view` JSON). For a **commit**, it is the post-`-next` goal in the
  `-agent-view` JSON `current_goal.lines`.
- `returncode` is 0 even when EC *rejects* a tactic — rejection shows up in the
  stdout text (e.g. `[TRY] accepted: False`, an error message, or `no progress`),
  NOT in the rc. Read the text.
- `source.ground_truth: false` on a panel goal means "parsed from EC pretty
  text", i.e. the panel re-rendered it — a prime place to check for mangling.

## How to report

Return a structured findings list. For each finding:
- **id / title**
- **severity**: blocker | high | medium | low | nit
- **dimension**: (your audit dimension)
- **run + turn**: e.g. `pr_G4_L4 turn_018`
- **evidence**: a short quote from `raw_ec.txt` (ground truth) AND the
  corresponding quote from `current_panel.md` / `current_view.json`
- **claim**: what the panel loses / distorts / fabricates vs EC
- **confidence**: high | medium | low (is this a real framework bug, or expected?)
- **suspected code**: file/function if you can point to it (optional)

End with a 3-5 line summary + your single most important finding. Prefer a few
**high-confidence, evidence-backed** findings over many speculative ones. If a
panel is faithful, say so explicitly (negative results are valuable).
