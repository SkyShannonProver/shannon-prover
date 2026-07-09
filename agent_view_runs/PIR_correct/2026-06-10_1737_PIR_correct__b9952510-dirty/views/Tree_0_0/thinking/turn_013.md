# Tree-0.0 · turn 13 · commit_tactic

<!-- session 50746433-7704-4ffd-84cc-4a2de77aaa16 · 2026-06-11T00:42:07.941Z -->

**Intent:** `commit_tactic`  
**Payload:** `move: hinv; rewrite /predT /= => hinv; smt(xorwA xorwC xorw0 xorwK).`

---

The `big` in `hinv` still uses `predT`; I'll normalize it to match the goal, then close with the xor-group lemmas.
