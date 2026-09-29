# Tree-0.1.0 · turn 10 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:27:15.886Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 13.`

---

Outer `if` resolved. Now I need freshness of the RO entries at `(n, ofintd 0)`: since `n = p.\`1 ∉ lenc`, the `inv_cpa` clause forces `(n,_) ∉ ROin.m` and `∉ ROout.m`. Resolve the `if` at line 13 (`x4 ∉ SplitC2.I1.RO.m`).
