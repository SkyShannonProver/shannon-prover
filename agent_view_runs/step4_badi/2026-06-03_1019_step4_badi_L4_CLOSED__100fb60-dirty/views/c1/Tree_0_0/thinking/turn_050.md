# Tree-0.0 · turn 50 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:17:22.695Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2 HP2; split; first by smt().`

---

I forgot to introduce the universally-bound memories — the goal is `forall &1 &2, pre => post`. Introduce them first, then split off the trivial equalities.
