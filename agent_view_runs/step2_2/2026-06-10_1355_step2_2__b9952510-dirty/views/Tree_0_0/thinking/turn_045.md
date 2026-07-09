# Tree-0.0 · turn 45 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:30:04.315Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite mapP; exists c => //=; rewrite mem_filter /=; exact hcmem.`

---

First subgoal is membership in the mapped/filtered list. Let me discharge it with `mapP`, witness `c`, and `mem_filter`.
