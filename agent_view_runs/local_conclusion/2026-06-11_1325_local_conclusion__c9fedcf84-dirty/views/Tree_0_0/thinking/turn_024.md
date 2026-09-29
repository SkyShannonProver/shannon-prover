# Tree-0.0 · turn 24 · commit_tactic

<!-- session 39e07884-1e1d-473e-a28f-5a1f3b3e3b24 · 2026-06-11T20:50:45.642Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> O enc_ll; islossless.`

---

The wrapper structure is clear: `RCPAa(...,O).distinguish` aliases to the inner adversary calling `A(Sim).distinguish` after `MAC.keygen()`. Trying the automated `islossless` tactic first.
