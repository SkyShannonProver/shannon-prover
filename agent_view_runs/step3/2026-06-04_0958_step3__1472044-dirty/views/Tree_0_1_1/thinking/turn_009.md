# Tree-0.1.1 · turn 9 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:35:50.585Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

The left is fully inlined. `x = (n, C.ofintd 0)`, so `SplitD.test x = (C.toint (C.ofintd 0) = 0)` which is true → the `if` takes the true branch (the poly split, sampling `r`, `s`, `e` fresh). Let me absorb the deterministic prefix with `sp`.
