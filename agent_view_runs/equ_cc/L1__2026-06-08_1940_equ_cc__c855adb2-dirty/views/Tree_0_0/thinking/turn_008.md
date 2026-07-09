# Tree-0.0 · turn 8 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:51:46.212Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hmul : block_size * (i{hr} - 1) < block_size * C.max_counter by smt(max_cipher_size_ok mulzC); have hb : i{hr} - 1 < C.max_counter by smt(ltr_pmul2l gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.`

---

Clean implication now. The goal is `! (C.toint (C.ofintd i) = 0)`. I'll intro, derive `size p ≥ 1`, get the strict product bound, divide by `block_size > 0` to bound `i-1 < max_counter`, then apply the round-trip lemma.
