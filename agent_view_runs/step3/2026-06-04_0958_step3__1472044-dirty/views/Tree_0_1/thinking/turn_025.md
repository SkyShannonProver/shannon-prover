# Tree-0.1 · turn 25 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:10:43.156Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; inline{2} CPA_CCA_Orcls(EncRnd).enc; inline{1} CPA_CCA_Orcls(RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))))).enc; sp; wp; inline{2} EncRnd.enc; inline{1} RealOrcls(GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO)))).enc; inline{1} GenChaChaPoly(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO))).enc.`

---

The then-branch. I'll replay the validated inline chain in one step to reach the `ChaCha.enc`/`Poly.mac` vs `cc`/random-tag alignment.
