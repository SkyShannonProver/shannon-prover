# Tree-0.0 · turn 4 · commit_tactic

<!-- session 7507390e-3397-450f-af34-e9dbd0b6cf44 · 2026-06-06T20:39:04.230Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h1 := parseK r p.`

---

The error text isn't in the manager result. Let me check the workspace view for `last_result`/`latest_observation`.

Right-to-left rewrite on the tuple is failing. Let me use forward reasoning, which is bulletproof here: derive the equation from `parseK` and the hypothesis.
