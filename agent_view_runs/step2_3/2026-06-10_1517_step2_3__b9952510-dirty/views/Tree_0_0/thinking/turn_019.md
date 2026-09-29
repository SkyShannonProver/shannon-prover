# Tree-0.0 · turn 19 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:44:34.905Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -(SplitC2.pr_RO_split (G9(A)) (fun _ (r:bool) => r) &m ()).`

---

First subgoal closed. Now the second: `Pr[UFCMA_poly(A, FinRO).main()] = Pr[Split1.IdealAll.MainD(G9(A), RO_Pair(I1.RO, I2.RO))]`. Mirroring the G8 term, I first un-split the RHS poly RO via `SplitC2.pr_RO_split`.
