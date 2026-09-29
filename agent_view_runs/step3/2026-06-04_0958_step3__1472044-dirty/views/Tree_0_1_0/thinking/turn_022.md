# Tree-0.1.0 · turn 22 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:35:42.397Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 13; first by move=> &m0; rnd; wp; skip => /=; rewrite /inv_cpa; smt().`

---

The `first by` chaining works. Resolve `if 13` and `if 17` the same way.
