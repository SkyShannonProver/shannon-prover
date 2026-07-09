# Tree-0.1.1 · turn 6 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:33:59.826Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2; rewrite /check_plaintext /valid_topol /inv_cpa /=; smt().`

---

Now it's a pure logical implication. The hypothesis carries everything needed; I just need to unfold `check_plaintext`/`valid_topol` (for the `size ≤ max_cipher_size` and non-membership facts) and `inv_cpa` (preserved since the maps are unchanged: `m_L = mr0 = SplitC2.I1.RO.m`), then let SMT discharge the tuple-projection chaining.
