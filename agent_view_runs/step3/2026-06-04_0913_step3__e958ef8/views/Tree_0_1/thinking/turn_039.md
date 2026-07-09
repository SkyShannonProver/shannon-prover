# Tree-0.1 · turn 39 · commit_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:38:07.094Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 17; 1: (by auto; smt()).`

---

The third inner `if` (extra-block RO) isn't covered by the invariant, but its result is discarded by `mk_rs_ofpair`, so I'll only force the `ROout` branch (position 17).
