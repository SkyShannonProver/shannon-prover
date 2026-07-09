# Tree-0.0 · turn 60 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:09:16.603Z -->

**Intent:** `probe_tactic`  
**Payload:** `right; rewrite /test_poly /=; move=> _; apply/List.hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/List.mapP; exists c; rewrite mem_filter /=; smt().`

---

The `smt(Hc Hn0)` couldn't resolve the names in that subcontext. Let me use plain `smt()` (hypotheses are in scope).
