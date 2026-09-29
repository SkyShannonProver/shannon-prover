# Tree-0.0 · turn 25 · commit_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:27:12.822Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.`

---

Left fully lowered: `ChaCha.enc` call + `Poly.mac` call + deterministic tail (and crucially `RealOrcls` does NOT touch `Mem.lc`). The two sides now align: `ChaCha.enc ~ EncRnd.cc` (→ `equ_cc`) and `Poly.mac ~ t<$dpoly_out` (tag coupling). Let me commit the left inline.
