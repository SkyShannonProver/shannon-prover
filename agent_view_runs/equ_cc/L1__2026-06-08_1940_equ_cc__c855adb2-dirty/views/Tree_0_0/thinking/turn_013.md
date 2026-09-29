# Tree-0.0 · turn 13 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:57:01.735Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; move=> &hr H; have hp1 : 1 <= size p{hr} by smt(size_eq0 size_ge0); have hc : size c{hr} = block_size * (i{hr} - 1) by smt(); have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; smt(C.ofintdK).`

---

Now I'll discharge this freshness side goal: reduce with `auto`, re-derive the `i ≤ max_counter` bound (same chain), then `smt` closes `(n0, ofintd i) ∉ ROF.m` via the freshness invariant clause and the round-trip lemma.
