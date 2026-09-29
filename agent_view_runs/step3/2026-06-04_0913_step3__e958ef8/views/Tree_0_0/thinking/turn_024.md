# Tree-0.0 · turn 24 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:26:08.083Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.`

---

The manager confirms `equ_cc` is the route for the `cc` call. Now I need to inline the left wrappers (`CPA_CCA_Orcls`, `RealOrcls`, `GenChaChaPoly.enc`) to expose the `ChaCha.enc` and `Poly.mac` calls. Let me probe the full left-side wrapper inline.
