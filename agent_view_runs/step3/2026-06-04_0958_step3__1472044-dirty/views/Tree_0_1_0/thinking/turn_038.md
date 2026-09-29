# Tree-0.1.0 · turn 38 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:45:22.557Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /inv_cpa /=; smt(mem_empty).`

---

`auto` cleaned it to a pure goal with `inv_cpa` over all-empty state. Unfold and discharge — empty-map membership is vacuous, the rest is reflexivity.
