# Tree-0.0 · turn 17 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:40:53.543Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr [[[eqk eqn eqgs Hrest] Hne] Hsz].`

---

`case` only splits the top `/\` once; the recursive bracket form should work but failed. Let me test whether the inner conjunction is actually 4 components (maybe I miscounted).
