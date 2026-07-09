# Tree-0.0 · turn 44 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:03:45.809Z -->

**Intent:** `probe_tactic`  
**Payload:** `do 4! (split; first by smt()).`

---

`split` works on the current goal but not 5 times — so the current goal IS the full conjunction (peelable 4×, leaving the `forall`). Let me probe peeling exactly 4.
