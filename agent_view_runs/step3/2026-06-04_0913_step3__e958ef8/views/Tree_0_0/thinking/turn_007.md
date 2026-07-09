# Tree-0.0 · turn 7 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:16:19.161Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{1} G8(BNR_Adv(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish.`

---

Now I'm at the call frontier. I need to inline the left's `G8→G6→G4→kg` distinguish wrappers (but NOT the adversary oracle bodies) to expose the same `CCA_CPA_Adv(BNR_Adv(A), ...).main` on both sides. Let me probe inlining the G8 distinguish wrapper.
