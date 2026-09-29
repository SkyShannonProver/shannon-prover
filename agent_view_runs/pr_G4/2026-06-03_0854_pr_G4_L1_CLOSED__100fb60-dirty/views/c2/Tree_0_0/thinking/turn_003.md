# Tree-0.0 · turn 3 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T16:56:17.418Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr _; rewrite expr2; smt().`

---

Remaining goals dropped to 8 — that branch is closed. New goal is a pure real-arithmetic inequality (actually an equality up to commutativity): `qD * (qD/order)^2 / (order-1) <= (qD/order)^2 * (qD/(order-1))`. The precondition is irrelevant. I'll expand `^2` and let smt close it, matching the established pattern in the replayed prefix.
