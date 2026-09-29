# Tree-0.1 · turn 17 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:48:00.884Z -->

**Intent:** `probe_tactic`  
**Payload:** `have -> : Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

Now the SplitC1 bridge. I'll reshape the RHS from the `G8`/`Split1.RO` form into the `Split0`/`G6`/`SplitC1` form via byequiv;sim, so `SplitC1.pr_RO_split` can then apply. Probing the bridge as a `have ->`:
