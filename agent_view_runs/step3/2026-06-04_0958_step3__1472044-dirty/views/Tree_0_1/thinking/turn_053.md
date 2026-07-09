# Tree-0.1 · turn 53 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:42:15.504Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto=> />; rewrite /SplitD.test /=; smt(C.gt0_max_counter).`

---

This side-goal needs `SplitD.test (n, ofintd 0)`, i.e. `C.toint (C.ofintd 0) = 0`. Compute the assignments and discharge with the subtype/counter facts.
