# Tree-0.0 · turn 17 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:51:41.113Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 7.`

---

Now back at the body with the else-branch. Next I'll force the `if (x1 ∉ ROF.m)` to **true** (the fresh-sample branch) via `rcondt{1} 7`. Freshness holds because `x1 = (n0, ofintd i)` and the invariant says any `(n0,c0) ∈ ROF.m` has `toint c0 < i`, while `toint(ofintd i) = i`.
