# Tree-0.0 · turn 6 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:45:03.876Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondf{1} 5.`

---

Inlining fully unfolded the RO chain. The key structure: `SplitD.test x = (toint x.2 = 0)`, and here `x = (n, ofintd i)` with `i >= 1` and `i <= max_counter` (derivable from the invariant), so `toint(ofintd i) = i ≠ 0` → the test is **false**, taking the `else` branch (the ROF lazy sample `r0 <$ dblock`). Let me force that branch with `rcondf{1}` on the `if` at position 5.
