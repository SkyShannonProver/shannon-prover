Initial manager handoff for this proof node.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
------------------------------------------------------------------------
0 <= i0 < N => Pr[PIR.main(i0) @ &m : res = a i0] = 1%r
```

---

## Probability Goal

**Probability structure:** Pr[...] equality

**Tactic applicability:**
- `byphoare` family for a single Pr bound
- `rewrite` family for a matching Pr lemma
- `byequiv` family if introducing a comparison program

---

## Status
remaining **1** · phase `opener`

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/demo_pir/l4_checked_action_surface/pir_correct/r01/2026-07-08_2049_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/demo_pir/l4_checked_action_surface/pir_correct/r01/2026-07-08_2049_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/demo_pir/l4_checked_action_surface/pir_correct/r01/2026-07-08_2049_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`
LEGAL_PROOF_SO_FAR: `artifacts/eval_suite/demo_pir/l4_checked_action_surface/pir_correct/r01/2026-07-08_2049_PIR_correct/iteration_1/node_memory/Tree_0_0/proof_so_far.md` (your full step-numbered committed proof — read it to pick a step for `amend_and_replay`/`undo_to_checkpoint`, or to re-orient)

Compaction recovery: if these exact paths are missing from your context, re-read `LEGAL_LATEST_FOLLOWUP` first and `LEGAL_PROOF_SO_FAR` only when you need accepted-history context. Submit your next advertised proof intent instead of using shell directory discovery for proof-state artifacts.
