# Tree-0.0 · turn 14 · commit_tactic

<!-- session 9c846476-96bc-4564-94eb-a9ec19803719 · 2026-06-09T00:02:54.750Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2 [-> [-> ->]]; rewrite /dec /get /=; smt().`

---

Same as `enc`, plus an `if` that matches the `dec` op's conditional. Intro, unfold, and close.
