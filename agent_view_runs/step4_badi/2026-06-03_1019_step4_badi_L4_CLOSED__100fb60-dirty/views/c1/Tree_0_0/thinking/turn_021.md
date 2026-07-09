# Tree-0.0 · turn 21 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:04:00.191Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(size_cat size_map nth_cat nth_map).`

---

Both programs are empty; this is now pure list/arithmetic logic. The residual needs `size_cat`, `size_map`, `nth_cat`, `nth_map` (for the `lbad1_R` size and the `nth` into the appended `map`), plus `b2i` reasoning from the range and `badi` pre-facts. Let me try `smt` with those lemmas.
