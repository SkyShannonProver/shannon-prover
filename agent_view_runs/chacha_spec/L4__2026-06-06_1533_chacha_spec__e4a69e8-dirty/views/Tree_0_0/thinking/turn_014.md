# Tree-0.0 · turn 14 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:39:37.986Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr [[[eqk eqn eqgs ge1i Heq] Hne] Hsz].`

---

`move=> &hr Hpre` works. The earlier failure was in the nested pattern. Let me isolate by testing the destructure pattern alone.
