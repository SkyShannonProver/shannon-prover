# Tree-0.0 · turn 59 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:09:00.786Z -->

**Intent:** `probe_tactic`  
**Payload:** `right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/List.mapP; exists c; rewrite mem_filter /=; smt(Hc Hn0).`

---

`apply/List.hasP` works. Now provide witness `(topol c.\`2 c.\`3, c.\`4)`, split, and close the membership branch with `List.mapP`.
