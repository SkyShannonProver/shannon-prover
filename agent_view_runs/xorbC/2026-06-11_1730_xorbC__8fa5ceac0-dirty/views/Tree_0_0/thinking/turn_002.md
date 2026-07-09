# Tree-0.0 · turn 2 · commit_tactic

<!-- session 81bcd8d8-bec8-4b2e-9107-7559bc2a14f8 · 2026-06-12T00:31:08.651Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b1 b2; apply/blockP=> i ge0_gti_n; rewrite !xorbE // xorwC.`

---

Sibling lemmas (xorbA, xorbK) show the proof pattern. Submitting the analogous tactic for commutativity.
