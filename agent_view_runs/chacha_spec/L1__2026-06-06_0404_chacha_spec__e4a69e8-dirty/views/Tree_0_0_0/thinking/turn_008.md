# Tree-0.0.0 · turn 8 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:22:43.959Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; auto => /#.`

---

The first subgoal is the `cc` contract. The proc body is just `return cc gs k n c`, so `proc; auto` with congruence closes it.
