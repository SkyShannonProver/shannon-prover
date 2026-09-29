# Tree-0.0 · turn 5 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:25:50.212Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (prD4 a &1).`

---

It was rejected but I can't see the error detail. Let me read the manager result.

The L1 view doesn't surface raw EC errors. The `byequiv ... by` likely left a residual subgoal, or `tt` is wrong. Let me sidestep the LHS entirely — `prD4` already computes `Pr[D4.sample]` directly.
