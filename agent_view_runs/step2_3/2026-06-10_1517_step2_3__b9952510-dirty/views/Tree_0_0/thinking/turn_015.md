# Tree-0.0 · turn 15 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:43:17.907Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[Split0.IdealAll.MainD(G6(A), ROT.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

LHS is now `MainD(G6(A), ROT.RO)`. Before the codomain split (stated over `Split0.IdealAll.RO`), I bridge `ROT.RO` to the identical `Split0.IdealAll.RO`.
