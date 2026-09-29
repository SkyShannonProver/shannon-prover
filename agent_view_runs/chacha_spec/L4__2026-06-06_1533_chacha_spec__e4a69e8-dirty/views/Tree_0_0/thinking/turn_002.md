# Tree-0.0 · turn 2 · inspect_context

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:35:02.101Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

I have the key lemmas (`gen_CTR_encrypt_bytes_cons`, `gen_CTR_encrypt_bytes0`, `take_xor` def) from the file. My plan: `proc` → `inline` the `cc` call → `while (inv) (size p)` with invariant `c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0`.

Let me get the phoare `while` form and enter the procedure.
