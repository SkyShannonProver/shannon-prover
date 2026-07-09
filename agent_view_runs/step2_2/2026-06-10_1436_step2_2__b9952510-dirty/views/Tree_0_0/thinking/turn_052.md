# Tree-0.0 · turn 52 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:07:33.261Z -->

**Intent:** `probe_tactic`  
**Payload:** `right; rewrite /test_poly hasP; exists (topol c.`2 c.`3, c.`4); split; first by apply/mapP; exists c; rewrite mem_filter Hc Hn0.`

---

Now the right disjunct: prove `test_poly` via `hasP`, witnessing with `c`. Let me probe the membership branch first (witness `c` is in the filtered/mapped list).
