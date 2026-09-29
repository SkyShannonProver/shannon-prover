# Tree-0.0 · turn 25 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:06:29.398Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2 H t0_0 _.`

---

`smt` can't chew the whole nested goal. I'll decompose manually. First introduce the memories, precondition, and the dead-sample quantifier to expose the conjunction.
