# Tree-0.1 · turn 45 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:37:52.122Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /check_plaintext /valid_topol; move=> />; smt().`

---

smt struggled — unfolding `inv_cpa` was counterproductive (it injects extra quantifiers; better to keep it opaque and let congruence match it against the hypothesis). Let me unfold only `check_plaintext`/`valid_topol` (to expose the size bound and freshness), introduce/substitute the equalities, then smt.
