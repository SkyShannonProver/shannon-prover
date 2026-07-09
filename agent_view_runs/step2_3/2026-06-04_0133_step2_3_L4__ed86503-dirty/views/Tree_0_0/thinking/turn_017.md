# Tree-0.0 · turn 17 · commit_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:52:23.326Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res].`

---

Names resolve. Committing the RHS SplitC2 peel; then I'll discharge the equality via `SplitC2.pr_RO_split`.
