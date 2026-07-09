# Tree-0.0 · turn 38 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:27:59.966Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`2.`

---

`rewrite h orbT` keeps failing — EC won't rewrite a boolean fact. Let me commit the `have` without an inline closer; this focuses the `test_poly` subgoal first, and I'll close the residual disjunction with `smt()` later.
