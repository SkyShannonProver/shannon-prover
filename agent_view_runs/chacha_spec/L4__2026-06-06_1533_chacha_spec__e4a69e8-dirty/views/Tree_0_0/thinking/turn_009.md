# Tree-0.0 · turn 9 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:36:47.154Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> sz; inline OCC(I).cc.`

---

Goal 1 is the loop body obligation. First introduce the variant bound (renaming to avoid clash with the program variable `z`), then handle the `cc` call. Let me probe introducing it and inlining.
