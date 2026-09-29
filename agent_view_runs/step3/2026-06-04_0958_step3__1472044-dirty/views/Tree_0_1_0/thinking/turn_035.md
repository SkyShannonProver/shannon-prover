# Tree-0.1.0 · turn 35 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:43:57.875Z -->

**Intent:** `commit_tactic`  
**Payload:** `skip; rewrite /inv_cpa /=; smt(mem_set get_setE).`

---

`sp` symbolically executed both `if`s, leaving a pure disjunctive implication with empty programs. The mixed cases (one side's guard taken, the other not) are contradictory via the `ndec`/`c` equalities inside `inv_cpa`; consistent cases give equal `p` and preserved invariant. Reduce and discharge.
