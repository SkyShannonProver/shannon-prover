# Tree-0.1 · turn 56 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:43:37.251Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr _; rewrite /SplitD.test /=; smt(C.gt0_max_counter).`

---

Now prove `C.toint (C.ofintd 0) = 0`. Introduce, unfold `test`, and discharge with the counter bound.
