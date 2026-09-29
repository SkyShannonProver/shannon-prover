# Tree-0.1 · turn 2 · commit_tactic

<!-- session 14f6a96e-ee89-4f03-a759-05808ef354f8 · 2026-06-12T00:42:02.493Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b; apply/blockP=> i ge0_gti_n; rewrite !andbE // andwK.`

---

`smt()` was rejected — `andb` may be a local definition. Let me check its definition in the file.
