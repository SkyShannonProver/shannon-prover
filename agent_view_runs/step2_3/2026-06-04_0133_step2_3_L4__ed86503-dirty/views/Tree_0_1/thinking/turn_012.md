# Tree-0.1 · turn 12 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:44:44.626Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(SplitC2.pr_RO_split (G8 A)).`

---

I have all four lemma signatures. Now I'll transform the RHS step by step. First, undo the SplitC2 codomain split (poly → poly_in⊗poly_out) on the RHS via `rewrite -SplitC2.pr_RO_split`. Probing:
