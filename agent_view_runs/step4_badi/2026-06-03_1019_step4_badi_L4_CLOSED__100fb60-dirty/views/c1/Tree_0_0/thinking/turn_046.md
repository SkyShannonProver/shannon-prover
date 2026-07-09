# Tree-0.0 · turn 46 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:14:48.957Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> HP2; split; first by smt().`

---

Now the post-condition glue: the equalities (from pre) plus the key implication `(nth lbad1 nth0).1 = .2 ⇒ badi_R`. The latter needs `neq_w1_w2` (out-of-range `nth` gives `(w1,w2)` with `w1≠w2`). Let me intro the pre and split off the trivial equalities first.
