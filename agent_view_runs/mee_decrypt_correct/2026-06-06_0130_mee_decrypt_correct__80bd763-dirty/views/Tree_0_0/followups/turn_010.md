## Requested: `inspect_context` — tactic_forms `while`

=== `while` tactic — argument forms === Current proof mode: ambient Form 1: while (INVARIANT) (VARIANT). Use when: One-sided phoare/probabilistic loop: the proof is already inside a `phoare` obligation and the loop needs both an invariant and a decreasing integer measure. Example: while (0 <= j <= N /\ oflist s = restr x j) (N - j). Note: Do not append `: p`, `(p)`, or any probability argument. The second parenthesized argument is the termination measure; EC generates the probability/body side obligations after this step. Form 2: while (INVARIANT). Use when: Symmetric while: both sides have while loops that advance together. Invariant holds between iterations. Example: while (={p, c, i, n} /\ OCC.gs{1} = RO.m{2}); auto. Form 3: while{1} (INVARIANT) (TERMINATION). Use when: One-sided while on LHS: LHS has a while, RHS doesn't (or has already been processed). Provide INVARIANT (holds each iteration) AND a TERMINATION measure (strictly decreasing integer that reaches 0 to end the loop). Example: while{1} (0 <= i <= n) (n - i). Note: Termination measure REQUIRED for one-sided while. EC won't accept without it. Form 4: while{2} (INVARIANT) (TERMINATION). Use when: One-sided while on...

## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

_mk: mK
_ek: block
_c: block list
------------------------------------------------------------------------
```
_…(+30 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

## Status
remaining **1** · phase `procedure_frontier` / `procedure_body`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `proc.` → accepted
- probe `inline *.` → probed (read-only; state unchanged)
- probe `inline PRPc.PseudoRP.fi.` → probed (read-only; state unchanged)
- probe `hoare.` → probed (read-only; state unchanged)
- probe `inline PseudoRP.fi.` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
