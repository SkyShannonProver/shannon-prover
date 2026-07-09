# Tree-0.0 · turn 24 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:05:49.088Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(size_cat size_map nth_cat nth_map).`

---

Now it's a pure goal (`forall &1 &2, pre => …`). The earlier `smt` failed because the goal was still an `equiv` judgement; now it should apply. Retrying with the list lemmas.
