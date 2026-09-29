# Tree-0.0.0 · turn 11 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:24:22.429Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -Heq (gen_CTR_encrypt_bytes_cons take_xor (cc gs0) k0 n0 iv p{hr} htake_xor) /take_xor //.`

---

Now: substitute via `-Heq`, unfold the one-step `cons`, and unfold `take_xor`. The added bytes are exactly `take_xor p z`, so it should close (modulo `++` associativity).
