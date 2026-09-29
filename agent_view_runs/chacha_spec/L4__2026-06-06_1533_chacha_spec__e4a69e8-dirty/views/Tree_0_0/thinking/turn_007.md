# Tree-0.0 · turn 7 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:36:09.016Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (k = k0 /\ n = n0 /\ OCC.gs = gs0 /\ 1 <= i /\ c ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i p = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) (size p).`

---

No error surfaced — the inline was just silently unusable. I don't actually need inline up front; the phoare `while` will leave a body obligation where I can handle the `cc` call. Let me probe the `while` with my invariant directly (the `while` loop is the last statement, so it applies, leaving the prefix `c<-[];i<-1` as a separate goal).
