# Tree-0.0 · turn 68 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:14:11.480Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge0 take0 in_nil).`

---

Now I'll prove this in steps. First: intro hypotheses and discharge the initial-invariant conjunct (`i{2}=0`, so `take 0 ns = []` makes the `forall` vacuous).
