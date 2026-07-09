# Tree-0.0 · turn 6 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:50:55.919Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv => //.`

---

No verified route here — manual lowering needed. The two sides run the same `CCA_game(A, …)` differing only in oracle implementation (functional `OChaChaPoly` vs loop-based `D.O` calling `IndBlock`). Let me probe `byequiv` to see the relational goal.
