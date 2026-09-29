# Tree-0.0 · turn 37 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:27:43.389Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`2; last by rewrite h orbT.`

---

The `by smt(h)` failed because `h` isn't accessible as a named lemma inside the `by` block. Let me switch to `have` (which puts `h` in context for the residual), prove `test_poly` first, then close the disjunction.
