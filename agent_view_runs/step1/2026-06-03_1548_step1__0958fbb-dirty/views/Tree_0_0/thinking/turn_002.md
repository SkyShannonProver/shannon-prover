# Tree-0.0 · turn 2 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:49:38.544Z -->

**Intent:** `commit_tactic`  
**Payload:** `congr.`

---

Let me read the full view to see what `congr.` produces (the `goal_after_probe`).

`congr.` splits the goal into two clean Pr-equalities (LHS↔IndBlock, and the IFinRO↔IndRO halves). This matches the natural structure. Let me commit it.
