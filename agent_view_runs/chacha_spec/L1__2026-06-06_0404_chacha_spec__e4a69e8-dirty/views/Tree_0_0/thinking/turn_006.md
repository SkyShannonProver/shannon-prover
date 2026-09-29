# Tree-0.0 · turn 6 · commit_tactic

<!-- session 7d9e4e8f-9d68-4e90-9a25-30821d7062c9 · 2026-06-06T11:09:59.127Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

Inline at top level is being rejected (likely because the only call is inside the loop body). Let me restructure: consume the two prelude assignments with `sp`, then apply `while`, and inline inside the body goal.
