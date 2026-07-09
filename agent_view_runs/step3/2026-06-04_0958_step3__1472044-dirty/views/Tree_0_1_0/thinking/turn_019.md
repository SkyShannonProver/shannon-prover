# Tree-0.1.0 · turn 19 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:34:58.371Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (n{1}), (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}); elim* => n0 mr0 ms0; call (equ_cc n0 mr0 ms0); skip; move=> &1 &2; rewrite /check_plaintext /valid_topol /=; smt().`

---

Now on subgoal 1 (the cc part) again, with the strengthened post. Replay the verified approach in one chain (it worked before; the new `p{1}=p{2}` conjunct is in the pre and discharged by the final smt).
