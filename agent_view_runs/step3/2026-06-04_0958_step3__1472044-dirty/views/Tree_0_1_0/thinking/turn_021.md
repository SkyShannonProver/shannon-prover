# Tree-0.1.0 · turn 21 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:35:30.524Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 9; first by move=> &m0; wp; skip; rewrite /SplitD.test /=; smt(@C).`

---

Same inlined state, now with `p{1}=p{2}` in pre. Resolve the outer `if` (line 9) and discharge its side goal in one chain.
