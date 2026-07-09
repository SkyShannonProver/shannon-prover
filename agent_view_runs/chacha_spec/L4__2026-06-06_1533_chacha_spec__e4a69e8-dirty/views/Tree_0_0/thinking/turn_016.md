# Tree-0.0 · turn 16 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:40:18.446Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr [[H1 Hne] Hsz]; case: H1 => eqk eqn eqgs ge1i Heq.`

---

`[[H1 Hne] Hsz]` works — the inline 5-name split was the issue. Let me split `H1` with `case` instead.
