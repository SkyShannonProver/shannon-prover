# Tree-0.0 · turn 17 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:01:22.708Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Now both sides fully unfolded in the range-true branch. The right has a dead `t0` sample (stmt 1, overwritten at stmt 6 by `t0 <- t1`) plus the live `t1` sample. I'll `wp` to absorb the trailing deterministic statements, then couple `t0{1}` with `t1{2}`, then dispose of the dead sample. Start with `wp`.
