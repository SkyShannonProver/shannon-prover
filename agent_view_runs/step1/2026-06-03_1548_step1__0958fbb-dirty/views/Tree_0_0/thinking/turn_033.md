# Tree-0.0 · turn 33 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:09:34.619Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq 1 1 : (t'{1} = t'{2} /\ t{1} = t{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c0{1} = c{2} /\ result{1} = result{2} /\ k{1} = IndBlock.k{2} /\ Mem.k{1} = IndBlock.k{2}).`

---

The linear script misaligned across the `seq`'s two goals (the `auto.`/`smt().` for part1 bled into part2). Let me commit just through the `seq` setup and handle each goal separately.
