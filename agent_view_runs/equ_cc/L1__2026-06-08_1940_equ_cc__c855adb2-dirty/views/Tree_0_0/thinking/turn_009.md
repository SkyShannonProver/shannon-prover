# Tree-0.0 · turn 9 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:53:19.034Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hc : size c{hr} = block_size * (i{hr} - 1) by smt(); have hmul : block_size * (i{hr} - 1) < block_size * C.max_counter by smt(max_cipher_size_ok mulzC); have hb : i{hr} - 1 < C.max_counter by smt(IntOrder.ltr_pmul2l gt0_block_size); rewrite /SplitD.test /= C.ofintdK 1:/# /#.`

---

The compound partially committed — only `hp1` landed, meaning the `hmul` step's smt failed. Let me verify the exact names of the multiplication-monotonicity and commutativity lemmas before retrying.

Both lemmas exist (`mulzC` in Int, `IntOrder.ltr_pmul2l` for the strict product). The harness commits each `;`-separated step incrementally, and `hp1` already landed. Let me continue: extract the `size c = block_size*(i-1)` equality explicitly, then the product bound, divide, and finish.
