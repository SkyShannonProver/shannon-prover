# Tree-0.1 · turn 4 · probe_tactic

<!-- session 794a61bb-7f1e-4330-b53e-4ab039bb259a · 2026-06-04T08:40:55.457Z -->

**Intent:** `probe_tactic`  
**Payload:** `congr.`

---

The interface gives sparse bridge info. Let me read the EasyCrypt `Split` theory source to understand the RO-split reduction lemmas I'll need, since the RHS uses `Split1.IdealAll.MainD` / `RO_Pair`.

I now understand the Split theory. The RHS reduces the block RO through: domain split (counter=0) → codomain split (poly/extra_block) → poly codomain split (poly_in/poly_out). The proof is a chain of `pr_RO_split` reductions plus byequiv/sim for the scheme reshaping. Let me consult the advisor on sequencing before committing tactics.

The advisor confirms my decomposition and the 4-layer peel. Let me start by probing `congr.` to confirm it splits the sum into the two aligned subgoals.
