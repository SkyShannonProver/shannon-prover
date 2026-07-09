# Tree-0.0 · turn 36 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:10:28.029Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> _ t0L _ /=; smt(size_cat size_map nth_cat nth_map size_ge0).`

---

Now introduce the leftover hyp + `t0L`, simplify, and close with `smt` (adding `size_ge0` since the false-range case needs `size lt ≥ 0`).
