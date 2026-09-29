# Tree-0.1 · turn 41 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:35:32.817Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (equ_cc witness mr0 ms0).`

---

Restored. Let me run a clean diagnostic: apply `equ_cc` with a deliberately *wrong* but well-typed `n0` (`witness`). If `call` **accepts** (producing an unprovable side-goal), then procedure matching works and my real issue is post/arg-related; if it **rejects**, matching is confirmed broken.
