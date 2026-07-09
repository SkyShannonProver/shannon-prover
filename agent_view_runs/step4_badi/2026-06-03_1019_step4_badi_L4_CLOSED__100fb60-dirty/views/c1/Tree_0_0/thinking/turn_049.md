# Tree-0.0 · turn 49 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:16:47.749Z -->

**Intent:** `commit_tactic`  
**Payload:** `split.`

---

`smt` times out on the whole goal, and `move` finds nothing to introduce — so the goal is the bare conjunction `A && B` (pre is ambient). Let me `split` it.
