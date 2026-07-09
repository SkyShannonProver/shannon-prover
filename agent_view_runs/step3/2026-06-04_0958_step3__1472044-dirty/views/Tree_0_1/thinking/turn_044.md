# Tree-0.1 · turn 44 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:37:02.133Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /inv_cpa /check_plaintext /valid_topol; smt().`

---

`call (equ_cc n0 mr0 ms0)` **accepted** with `n0` as a logical variable. The ChaCha→cc hop is done; the remaining goal is the pure logical obligation (pre ⇒ `equ_cc`'s precondition ∧ (its postcondition ⇒ my intermediate)). Everything follows from the `nap` equality chain, `check_plaintext`, and the carried invariant. Let me discharge by unfolding the ops and calling smt.
