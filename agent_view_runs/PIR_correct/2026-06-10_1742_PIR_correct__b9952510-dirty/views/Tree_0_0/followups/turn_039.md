## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
z: int
```
_…(+20 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `big`
- `int`
- `PIR.s`
- `zerow`

**Visible hypotheses:**
- `hi0: 0 <= i0 < N`
- `H: (((0 <= j{hr} <= N /\`
- `hv: v \in {0,1}`
- `hji: j{hr} = i{hr}`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `rewrite -/predT; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` — NO PROGRESS — EasyCrypt ACCEPTED this probe but it did not change the goal, so nothing was committed (it auto-reverts). This is NOT a syntax or type error — there is no error to fix. The tactic is a no-op at this goal (e.g. the call is alr… (The committed EasyCrypt proof state was not changed.)

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `case v => hv2.` → accepted
- probe `rewrite big_cons /=; rewrite /predT in H; smt(xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)
- commit `rewrite big_cons /=; rewrite /predT in H; smt(xorwA xorwC xorw0 xorwK).` → REJECTED: structural-fingerprint-equal
- probe `rewrite BBS.big_cons /=.` → probed (read-only; state unchanged) (×2)
- probe `rewrite BBS.big_cons.` → probed (read-only; state unchanged)
- probe `rewrite /predT in H; smt(big_cons xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)
- probe `rewrite -/predT.` → probed (read-only; state unchanged)
- probe `smt(BBS.big_cons xorwA xorwC xorw0).` → REJECTED: cannot prove goal (strict)
- probe `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
