## Requested: `inspect_context` — tactic_forms `call`

=== `call` tactic — argument forms === Current proof mode: ambient Form 1: call LEMMA. Use when: An equiv lemma already proves the procedure correspondence you need. This is the preferred form when available — EC closes the whole adversary/oracle call in one step. Example: call H_proc. (* uses a pre-declared equiv handle *) Note: EC unifies the pRHL call's LHS/RHS procedure targets against LEMMA's statement. If that succeeds, the call is fully handled. Form 2: call (_: INVARIANT). Use when: No pre-existing equiv lemma matches — you must provide the oracle invariant manually. EC generates oracle-equiv subgoals (one per oracle procedure the adversary may call). Example: call (_: ={Mem.k, Mem.log} /\ StLSke.gs{1} = RO.m{2}). Note: Two pre-flight checks before writing the invariant: (a) Is there already a named equiv lemma that proves this correspondence? Run `-file-index` or check `strategic_helpers[equiv]` in your plan's context brief — if yes, prefer Form 1 (`call LEMMA.`) instead of re-deriving via invariant. (b) For an outer call to an abstract adversary's main (e.g. `A.main`, `BNR_Adv(A).main`), do NOT include `={glob A}` in the invariant. EC handles glob A implicitly via the...

## 🎯 Current Goal (unchanged)
```
Current goal (remaining: 5)

Type variables: <none>

_mk: mK
_ek: block
_c: block list
z: int
```
_…(+30 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Status
remaining **5** · phase `procedure_frontier` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> z.` → accepted
- probe `inline PRPc.PseudoRP.fi.` → probed (read-only; state unchanged)
- probe `inline *.` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
