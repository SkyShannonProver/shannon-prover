# Tree-0.0 · turn 7 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T17:58:59.302Z -->

**Intent:** `commit_tactic`  
**Payload:** `case (UFCMA.cbad1{1} < qenc /\ size lt{1} <= qdec).`

---

Prefix closed. Now I'm at the core tail: `t0 <$ dpoly_out; if (guard) {...}` with the divergent instrumentation on the right. The outer guard is coupled (`={UFCMA.cbad1}`, `={lt}`), so I'll case-split on it.
