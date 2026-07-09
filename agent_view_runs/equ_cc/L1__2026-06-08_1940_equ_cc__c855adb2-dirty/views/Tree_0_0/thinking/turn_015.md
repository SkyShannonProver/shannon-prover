# Tree-0.0 · turn 15 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:58:05.213Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; move=> r0_0 _; smt(C.ofintdK).`

---

`hc` landed (the earlier stall was a chain artifact). Now the bound and the freshness contradiction.
