# Tree-0.1.1 · turn 16 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:42:22.526Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 2.`

---

`r4` is now universally quantified away. Now I'll resolve the two relevant `if` guards to their true branches (the `(n,0)` entry is fresh in both `SplitC2.I1.RO.m` and `SplitC2.I2.RO.m` by `inv_cpa` + `n ∉ lenc`). Starting with the `x4`/`ROin` guard at position 2.
