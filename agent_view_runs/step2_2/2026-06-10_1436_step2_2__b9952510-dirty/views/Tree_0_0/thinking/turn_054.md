# Tree-0.0 · turn 54 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:08:10.276Z -->

**Intent:** `probe_tactic`  
**Payload:** `right; rewrite /test_poly /=; move=> _; apply/hasP; exists (topol c.`2 c.`3, c.`4); split; first by rewrite mem_filter; smt(Hc Hn0).`

---

`right` turned it into `!forged{hr} => has (...)`, and `has` is now bare so `hasP`/`mapP` apply. Let me probe through the membership branch to expose the tag-equation leaf.
