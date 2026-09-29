# Tree-0.0 · turn 20 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:53:30.159Z -->

**Intent:** `probe_tactic`  
**Payload:** `have ->: Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G6(A), SplitC1.RO_Pair(SplitC1.I1.RO, SplitC1.I2.RO)).distinguish() @ &m : res].`

---

SplitC2 layer peeled. Now the clone-bridge spike the advisor flagged: relate `Split1.MainD(G8(A), Split1.RO)` to `Split0.MainD(G6(A), SplitC1.RO_Pair(I1,I2))` — they differ only by the poly-RO clone (`Split1.RO` ↔ `SplitC1.I1.RO`) plus G8 unfolding to G6. Let me probe the `have ->` to confirm names resolve.
