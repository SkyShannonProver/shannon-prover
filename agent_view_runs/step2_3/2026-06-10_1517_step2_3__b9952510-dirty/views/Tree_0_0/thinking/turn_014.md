# Tree-0.0 · turn 14 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:42:59.404Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[Split0.IdealAll.MainD(G4(A), RO_DOM(ROT.RO, ROF.RO)).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), ROT.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

LHS is now in `RO_DOM` form. Reformulating to the `G6` module (which inits `ROF` internally), equivalent by init-reordering.
