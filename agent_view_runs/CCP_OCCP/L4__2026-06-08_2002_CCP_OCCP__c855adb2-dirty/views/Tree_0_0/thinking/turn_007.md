# Tree-0.0 · turn 7 · commit_tactic

<!-- session 7fdb1d9e-9355-4ba1-84e5-b9fd99e067a4 · 2026-06-09T03:04:56.402Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Now the substantive subgoal: `enc`. LHS calls `ChaCha(OCC(I)).enc` and `Poly(OCC(I)).mac` procedures; RHS uses the operator forms `gen_CTR_encrypt_bytes`/`genpoly1305`. The `chacha_spec` and `poly_spec` phoare lemmas are the bridge. Let me step in.
