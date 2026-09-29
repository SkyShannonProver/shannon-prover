# Tree-0.0 · turn 3 · commit_tactic

<!-- session 382c4036-5d4e-4165-b059-b68997d944c4 · 2026-06-04T17:00:09.502Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish.`

---

Now I need to inline the LHS distinguish wrapper chain (G8→G6→G4) to expose the inner `CCA_CPA_Adv(BNR_Adv(A), ...).main()` call, without inlining the oracle bodies. Let me inline the top wrapper first to learn the concretized naming.
