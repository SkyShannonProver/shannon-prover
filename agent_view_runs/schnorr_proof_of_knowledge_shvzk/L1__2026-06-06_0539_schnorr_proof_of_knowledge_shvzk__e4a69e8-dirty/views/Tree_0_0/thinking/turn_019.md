# Tree-0.0 · turn 19 · commit_tactic

<!-- session 5a34e25e-6cb0-4b52-a73e-3dd4b84fb232 · 2026-06-06T12:56:57.837Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> _; rewrite log_bij !(loggK, logDr, logrzM); ring.`

---

The combined tactic left 3 residual goals (the `first` only closed one branch's conjunct). Let me close them one at a time. Current: the zero-branch group equation.
