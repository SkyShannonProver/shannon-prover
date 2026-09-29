# Tree-0.0 · turn 23 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:43:59.891Z -->

**Intent:** `probe_tactic`  
**Payload:** `have Hnil: forall s, take_xor [] s = [] by move=> s; rewrite /take_xor /=.`

---

That was a transient probe-tool/backend failure (not an EC rejection). Let me retry, dropping the explicit type annotation to let EC infer it.
