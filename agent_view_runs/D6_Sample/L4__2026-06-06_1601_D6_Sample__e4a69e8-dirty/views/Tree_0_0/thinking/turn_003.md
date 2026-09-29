# Tree-0.0 · turn 3 · commit_tactic

<!-- session 5030107a-3fc2-4799-b73b-6171eedb749b · 2026-06-06T23:02:53.326Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Bodies are clear. LHS has an extra `r <- 5` then `while (5 <= r)`; RHS is `while (! 1 <= r <= 4)`, both bodies `r <$ [1..6]`. The guards are equal on the support [1..6]. Let me commit `proc`.
