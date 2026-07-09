# Tree-0.1 · turn 32 · commit_tactic

<!-- session dbe52ca4-5aee-47b2-86f1-a4030a610470 · 2026-07-09T03:59:35.582Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (xorwC (a i0) B) !xorwA.`

---

SMT can't do the AC cancellation. I'll normalize the XOR expression by hand. First reorder and left-associate.
