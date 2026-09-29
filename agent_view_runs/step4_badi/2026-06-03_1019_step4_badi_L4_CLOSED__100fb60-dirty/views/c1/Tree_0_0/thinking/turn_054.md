# Tree-0.0 · turn 54 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:19:12.855Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2 HP2; split; first by smt().`

---

Now it's `forall &1 &2, pre => (A && B)`. Introduce, split, close the trivial equalities `A` from the precondition.
