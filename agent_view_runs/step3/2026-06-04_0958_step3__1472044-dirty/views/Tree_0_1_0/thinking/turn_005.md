# Tree-0.1.0 · turn 5 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:23:31.694Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2; rewrite /check_plaintext /valid_topol /=; smt().`

---

Now it's a pure logical implication. Everything needed is derivable from the pre, but `check_plaintext`/`valid_topol` must be unfolded to expose `size p2 ≤ max_cipher_size` and `!n ∈ lenc`. Let me intro the memories, unfold, and discharge with smt.
