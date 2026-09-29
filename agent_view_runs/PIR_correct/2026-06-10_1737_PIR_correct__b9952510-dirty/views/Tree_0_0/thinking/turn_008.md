# Tree-0.0 · turn 8 · commit_tactic

<!-- session 50746433-7704-4ffd-84cc-4a2de77aaa16 · 2026-06-11T00:41:19.433Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr ge0 leN hinv jltN; rewrite !big_cons /=; smt(xorwA xorwC xorw0 xorwK dbool_ll).`

---

smt couldn't unfold the conditional `big_cons`. Let me introduce the context and rewrite `big_cons` explicitly (simplifying the `predT` guard) before smt.
