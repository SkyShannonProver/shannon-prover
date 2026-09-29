# Tree-0.0 · turn 43 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:03:09.417Z -->

**Intent:** `probe_tactic`  
**Payload:** `do 5! (split; first by smt()).`

---

The commit was accepted but the goal still shows the full conjunction (the chained `0 <= i+1 <= size ns` likely added an extra split level). Let me probe peeling all bookkeeping conjuncts to isolate the `forall`.
