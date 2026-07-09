# Tree-0.1.0 · turn 6 · probe_tactic

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:31:54.054Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp.`

---

`if` is rejected with "invalid first instruction" — so the residual program's first statement is not a conditional (it's an assignment/sample/set). `auto` fails only because it tries to *close* the resulting VC and can't. I need a program-processing tactic that doesn't attempt closure. Let me probe `sp` (push leading assignments/samples forward).
