# Tree-0.0 · turn 48 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:16:07.207Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(neq_w1_w2 nth_default).`

---

The error is "nothing to introduce" — the memories are already bound, so this is a pure relational implication. It needs `neq_w1_w2` plus the out-of-range `nth` fact (`nth_default`). Let me discharge with `smt` directly.
