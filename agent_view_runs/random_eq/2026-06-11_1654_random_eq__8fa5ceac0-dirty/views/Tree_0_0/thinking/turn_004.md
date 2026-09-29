# Tree-0.0 · turn 4 · commit_tactic

<!-- session 1959f737-444b-4631-b310-fb150d0581af · 2026-06-11T23:56:58.497Z -->

**Intent:** `commit_tactic`  
**Payload:** `by auto=> /=; smt(size_ge0).`

---

Side goal: prove `0 ≤ size p0` after the prefix. Discharging via smt with `size_ge0`.
