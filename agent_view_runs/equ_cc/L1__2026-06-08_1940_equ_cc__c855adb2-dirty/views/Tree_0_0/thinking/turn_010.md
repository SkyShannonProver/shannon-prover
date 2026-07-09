# Tree-0.0 · turn 10 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:53:56.981Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h1 : block_size * (i{hr} - 1) < C.max_counter * block_size by smt(max_cipher_size_ok); have hb : i{hr} - 1 < C.max_counter by smt(IntOrder.ltr_pmul2r mulzC gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.`

---

`hc` landed but `hmul` failed — the issue was writing `block_size * C.max_counter` (forcing a commutativity match Z3 wouldn't make). Let me state the bound in the same orientation as `max_cipher_size_ok` (`C.max_counter * block_size`, pure linear over atoms), then divide using `ltr_pmul2r`.
