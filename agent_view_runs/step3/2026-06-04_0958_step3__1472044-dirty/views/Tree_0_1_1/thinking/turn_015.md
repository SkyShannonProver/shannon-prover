# Tree-0.1.1 · turn 15 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:40:17.594Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd{1}.`

---

`wp` absorbed the trailing `if` into the postcondition as an if-then-else; now the last left statement is the `r4 <$ dextra_block` sample. Since `mk_rs (ofpair(r1, e)) = (r10, r20)` regardless of `e` (by `mk_rs_ofpair`), `r4` is irrelevant — I dispose it one-sided (now it *is* the last left sample, so `rnd{1}` applies).
