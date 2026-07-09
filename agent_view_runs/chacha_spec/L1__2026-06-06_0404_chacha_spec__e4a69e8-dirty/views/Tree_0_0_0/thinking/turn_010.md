# Tree-0.0.0 · turn 10 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:23:53.915Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr Heq Hne; split; last by smt(size_drop gt0_block_size size_eq0 size_ge0).`

---

Clean goal now. Let me intro, split off the size obligation (closed by `size_drop`), and keep the equation.
