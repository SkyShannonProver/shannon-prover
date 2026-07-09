# Tree-0.1 · turn 25 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:50:07.085Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(FiniteRO.pr_RO_FinRO_D (fun _ => Block.dblock_ll) (G4(A)) &m () (fun b => b)) /=.`

---

LHS now needs FinRO→RO conversion (top-level), then a final clone bridge. Probing the `pr_RO_FinRO_D` rewrite on the LHS:
