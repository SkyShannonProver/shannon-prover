# Tree-0.0 · turn 1 · inspect_context

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:34:21.766Z -->

**Intent:** `inspect_context`  
**Payload:** `lemma_index`

---

I'll start by orienting myself — reading the latest workspace view and any existing node memory before composing.

This is a fresh node — no tactics committed yet. I'm proving a phoare=1 functional-correctness lemma for `ChaCha(OCC(I)).enc`. Let me analyze the structure.

The procedure is a `while (p <> [])` loop appending `take (size p) (bytes_of_block (extend p +^ z))` = exactly `take_xor p z` where `z = cc gs k n (C.ofintd i)`. The functional spec `gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0` unfolds (via `gen_CTR_encrypt_bytes_cons`) into precisely this iteration. So this needs `proc`, a `while` invariant tying `(c,p,i)` to the spec, with `size p` as the termination variant.

Let me get the exact lemma signatures and probe the entry.
