# Tree-0.1.0 · turn 11 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:27:22.988Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m0; rnd; wp; skip => /=; rewrite /inv_cpa; smt().`

---

Side goal: `x4 = (n, ofintd 0) ∉ ROin.m` from the invariant (`n ∉ lenc`). Skip the trailing sample, substitute, unfold `inv_cpa`, discharge.
