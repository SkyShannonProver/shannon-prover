# Tree-0.0 · turn 3 · commit_tactic

<!-- session 2a906b42-b9e2-4eca-b55e-ed59a3848696 · 2026-06-11T15:09:18.671Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 17; first by auto => />; smt(mem_set).`

---

Both first guards resolved. Now the left `if` at 17 — `(t2,0)` is still fresh after the `(t1,0)` write, needs `mem_set`.
