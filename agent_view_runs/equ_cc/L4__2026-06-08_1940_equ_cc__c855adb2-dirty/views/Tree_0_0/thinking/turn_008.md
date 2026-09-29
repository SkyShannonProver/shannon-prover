# Tree-0.0 · turn 8 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:48:03.622Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m; wp; skip; rewrite /SplitD.test /=; smt(C.ofintdK max_cipher_size_ok gt0_block_size size_ge0 size_eq0).`

---

Confirmed: `C.ofintdK: 0 <= x < max_counter+1 => toint (ofintd x) = x`. Now I'll discharge the rcondf side-goal. After `wp; skip`, unfold `SplitD.test` and let smt derive `i <= max_counter` (from `(i-1)*block_size = size c`, `size c + size p <= max_cipher <= max_counter*block_size`, `size p >= 1`).
