# Tree-0.0 · turn 41 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T22:00:43.952Z -->

**Intent:** `probe_tactic`  
**Payload:** `split; last by smt(); do 4! (split; first by smt()).`

---

Let me peel off the arithmetic and bookkeeping conjuncts, leaving just the key `forall c` obligation.
