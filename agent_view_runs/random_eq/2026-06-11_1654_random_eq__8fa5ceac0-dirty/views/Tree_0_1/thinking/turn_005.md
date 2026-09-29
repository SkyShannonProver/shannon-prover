# Tree-0.1 · turn 5 · commit_tactic

<!-- session b4482fc9-866e-4e90-966b-ec3a4770f7b9 · 2026-06-11T23:56:57.151Z -->

**Intent:** `commit_tactic`  
**Payload:** `by auto=> /=; smt(size_ge0).`

---

Side condition: prove `i <= size p0` after the prefix. `auto` + smt should close it.
