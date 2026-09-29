# Tree-0.0.0 · turn 1 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:19:53.718Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline OCC(I).cc.`

---

I've read the state. I'm proving the `chacha_spec` phoare lemma; the replay set up `proc; sp; while (inv) (size p)` and I'm now at the loop-body goal (bound `[=] 1%r`), with the post-loop goal still pending. Let me look at the key lemma I'll need.

My plan: the loop body is deterministic (the `cc` oracle just returns `cc gs k n c`, no sampling), so `inline 1; wp; skip` reduces it to a pure implication. The invariant equation is preserved via `gen_CTR_encrypt_bytes_cons` (the added `take (size p) (bytes_of_block (extend p +^ z))` is exactly `take_xor p z`), and the variant decreases by `size_drop`/`gt0_block_size`. Let me get a second opinion before committing.

Plan confirmed. Let me start by inlining the `cc` call.
