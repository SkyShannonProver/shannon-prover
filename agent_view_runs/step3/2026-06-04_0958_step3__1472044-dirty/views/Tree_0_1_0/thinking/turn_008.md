# Tree-0.1.0 · turn 8 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:25:59.393Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 9.`

---

The left is fully inlined. Since `c4 = C.ofintd 0`, `SplitD.test x` (i.e. `C.toint x.\`2 = 0`) is true, so the else branch is dead. Resolve the outer `if` to its then-branch.
