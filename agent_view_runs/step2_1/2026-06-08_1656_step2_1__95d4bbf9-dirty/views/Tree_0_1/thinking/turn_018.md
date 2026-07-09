# Tree-0.1 · turn 18 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:04:25.624Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &2; rewrite /dec /get; case: (c{2}) => n a c0 t /=; smt().`

---

The `dec` reduces to two implications matching the `if` branches. Let me unfold `dec`/`get`, destruct the tuple, and discharge the conditional logic.
