# Tree-0.0.r2 · turn 1 · probe_tactic

<!-- session 9c6ff196-6193-4d35-b3d1-45aa33af05e6 · 2026-06-10T22:15:55.460Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]]; apply (IH c); first by rewrite -Hlc'. by rewrite Hgs'. rewrite take_oversize 1:/#; rewrite Hns' mem_undup; apply/mapP; exists c; rewrite -Hlc'.`

---

I'll start by probing an `smt` close for this pure-logic post-loop goal, after introducing the hypotheses.
