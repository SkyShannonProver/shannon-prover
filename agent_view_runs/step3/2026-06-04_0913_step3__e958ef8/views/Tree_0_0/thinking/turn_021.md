# Tree-0.0 · turn 21 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:24:35.576Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{2} CPA_CCA_Orcls(EncRnd).enc.`

---

Now the then-branch: the inner `CPA_CCA_Orcls(...).enc` calls differ only in the underlying scheme. I must inline the wrapper layers (`CPA_CCA_Orcls`, `RealOrcls`, `GenChaChaPoly.enc`, `EncRnd.enc`) WITHOUT inlining the while-loop-bearing `ChaCha.enc`/`EncRnd.cc`/`Poly.mac`, so I can then `call equ_cc`. Let me first look up the `CPA_CCA_Orcls.enc` structure.
