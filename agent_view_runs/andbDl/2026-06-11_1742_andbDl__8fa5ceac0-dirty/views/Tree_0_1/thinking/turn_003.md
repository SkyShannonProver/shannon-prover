# Tree-0.1 · turn 3 · commit_tactic

<!-- session 27d2ca88-150d-455e-a5dd-9984484c0677 · 2026-06-12T00:43:59.233Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> x y z; apply/blockP=> i ge0_gti_n; rewrite !(andbE, xorbE) // andwDl.`

---

The goal is over `block`, not `bool` — `andb`/`+^` are block-level ops. Let me check their definitions in the target file (allowed under eval rules).
