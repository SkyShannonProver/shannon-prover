# Tree-0.0 · turn 6 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T16:57:24.646Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr _; rewrite (_: 3 = 2 + 1) // exprS // expr2; smt().`

---

Remaining 6 — another arithmetic equality-as-inequality: `qD * ((qD/order)^2 * (qD/(order-1)))/order ≤ (qD/order)^3 * (qD/(order-1))`. Both sides are equal; I need to expand the `^3` and `^2` before smt can see it. I'll rewrite `3` as `2+1`, unfold via `exprS`/`expr2`, then close.
