# Tree-0.1.0 · turn 36 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:44:47.134Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; rnd{1}; wp; skip; rewrite /inv_cpa /=; smt(mem_empty in_emptyE emptyE).`

---

`dec` is done — this is the final goal: the `distinguish` main (init RO maps + sample `k` + init `Mem`/`BNR`, then the adversary `call` framing). I need to establish the initial `inv_cpa` (all maps/logs empty, so equalities hold and freshness is vacuous) and the trivial `result_L=result_R` framing. Execute the init (one-sided `k` sample) and discharge.
