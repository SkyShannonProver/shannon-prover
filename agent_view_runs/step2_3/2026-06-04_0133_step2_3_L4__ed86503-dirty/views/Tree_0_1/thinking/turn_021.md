# Tree-0.1 · turn 21 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:49:02.173Z -->

**Intent:** `probe_tactic`  
**Payload:** `have -> : Pr[Split0.IdealAll.MainD(G6(A), Split0.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G4(A), SplitD.RO_DOM(SplitD.ROT.RO, SplitD.ROF.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

RHS collapsed cleanly. Now the SplitDom bridge: reshape `G6/Split0.RO` into the `G4`/`RO_DOM` form via byequiv;sim. Probing:
