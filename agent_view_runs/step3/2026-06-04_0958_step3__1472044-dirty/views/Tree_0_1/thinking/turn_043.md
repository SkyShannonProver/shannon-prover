# Tree-0.1 · turn 43 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:36:12.806Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (p{1}.`1); elim* => n0; call (equ_cc n0 mr0 ms0).`

---

Back at the clean head with `mr0`/`ms0` as logical vars. The fix is to make `n0` a logical variable too. Generalize the nonce and apply.
