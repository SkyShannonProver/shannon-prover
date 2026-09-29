# Tree-0.0 · turn 16 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:52:09.169Z -->

**Intent:** `probe_tactic`  
**Payload:** `have ->: Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] = Pr[Split1.IdealAll.MainD(G8(A), Split1.IdealAll.RO).distinguish() @ &m : res].`

---

FinRO→RO done; LHS is now `MainD(G4,RO)` (with a trivial `(fun r=>r) res` redex I'll let byequiv absorb later). Now I'll peel the RHS split layers via `pr_RO_split`. Starting with the outermost SplitC2 (poly→poly_in×poly_out). Let me probe a `have ->` rewriting the RHS to the unsplit `Split1.RO` form to confirm names resolve.
