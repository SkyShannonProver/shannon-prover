# Tree-0.0 · turn 12 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:56:21.777Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 7.`

---

The dead branch is eliminated (now down to 2 goals). The body's live path samples `r0 <$ dblock` then conditionally stores it. The freshness invariant guarantees `(n0, ofintd i)` is not yet in `ROF.m`, so the `if (x1 \notin ROF.m)` always takes the store branch. Let me assert that with `rcondt{1} 7`.
