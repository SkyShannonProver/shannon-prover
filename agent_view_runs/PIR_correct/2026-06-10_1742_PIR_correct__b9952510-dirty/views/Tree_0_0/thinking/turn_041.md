# Tree-0.0 · turn 41 · commit_tactic

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:06:59.990Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /predT in H; split.`

---

`rewrite /predT in H` works and now `H` matches the goal's `fun (_ : int) => true` form. Let me commit this (it also splits off the arithmetic tail), locking in the predicate match.
