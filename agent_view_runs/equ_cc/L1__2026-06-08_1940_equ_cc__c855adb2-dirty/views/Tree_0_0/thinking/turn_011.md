# Tree-0.0 · turn 11 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:55:36.478Z -->

**Intent:** `commit_tactic`  
**Payload:** `move: h1; rewrite (mulzC block_size (i{hr} - 1)) (IntOrder.ltr_pmul2r block_size gt0_block_size) => hb; rewrite /SplitD.test /=; smt(C.ofintdK).`

---

`h1` landed; the `hb` division step failed in smt (nonlinear). Let me prove `hb` by explicit rewriting: generalize `h1` into the goal, flip the product with `mulzC`, cancel `block_size` via `ltr_pmul2r`, then finish the `test` goal with smt using the round-trip lemma.
