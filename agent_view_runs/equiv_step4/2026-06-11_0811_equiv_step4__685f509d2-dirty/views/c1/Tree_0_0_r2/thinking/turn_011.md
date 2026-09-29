# Tree-0.0.r2 · turn 11 · commit_tactic

<!-- session fca01fed-86e4-4234-8933-7ebe441664f7 · 2026-06-11T08:25:47.410Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move => h6; rewrite !get_set_sameE set_set_neqE 1:/#.`

---

Now the live branch. Rewrite the same-key lookups under the lambdas, then commute the two updates with `set_set_neqE`.
