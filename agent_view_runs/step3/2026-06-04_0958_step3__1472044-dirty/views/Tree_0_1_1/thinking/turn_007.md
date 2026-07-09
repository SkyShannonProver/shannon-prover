# Tree-0.1.1 · turn 7 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:34:48.326Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

First subgoal closed (remaining: 4). The focused goal is now the second `seq` part — the tag/MAC step: `Poly(...).mac(k,n,a,c2)` on the left versus a fresh `t <$ dpoly_out` on the right, plus the ciphertext assembly. Let me first `wp` to absorb the deterministic tuple assignments into the postcondition.
