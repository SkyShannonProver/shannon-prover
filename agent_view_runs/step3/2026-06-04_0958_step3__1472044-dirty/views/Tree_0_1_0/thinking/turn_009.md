# Tree-0.1.0 · turn 9 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:26:36.037Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m0; wp; skip; rewrite /SplitD.test /=; smt(@C).`

---

The side goal: prove `SplitD.test x` holds, i.e. `C.toint (C.ofintd 0) = 0`. Intro, substitute assignments, unfold `test`, and discharge with the subtype facts.
