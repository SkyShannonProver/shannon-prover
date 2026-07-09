# Tree-0.0 · turn 17 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:44:02.107Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

Final reformulation of the first subgoal: bridge to the `G8` form with `Split1.IdealAll.RO` (combining the G8 wrapping and the poly-clone bridge).
