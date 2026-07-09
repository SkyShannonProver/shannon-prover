# Tree-0.0 · turn 3 · commit_tactic

<!-- session 7b1d76ba-abdb-4c35-a0ea-9d5809e0bb97 · 2026-06-11T13:56:38.535Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; inline *; auto.`

---

The `if` step didn't parse for `dec` — its body is assignment-only after inlining, so plain `auto` should traverse it.
