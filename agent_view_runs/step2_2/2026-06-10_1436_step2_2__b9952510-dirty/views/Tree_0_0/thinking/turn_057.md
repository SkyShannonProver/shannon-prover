# Tree-0.0 · turn 57 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:08:39.119Z -->

**Intent:** `probe_tactic`  
**Payload:** `right; rewrite /test_poly /=; move=> _; rewrite List.hasP; exists (topol c.`2 c.`3, c.`4); split; first by rewrite mem_filter; smt(Hc Hn0).`

---

Two `hasP` lemmas exist (fmap and List); `apply/hasP` picks the wrong one. Let me use `List.hasP` explicitly.
