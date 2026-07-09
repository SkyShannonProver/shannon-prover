# Tree-0.0 · turn 2 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:27:59.639Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr ? u u' r0 r'0 ?; smt(map_f).`

---

The `conseq` produced the implication subgoal (tuple membership ⟹ projection memberships). This is just `map_f`. Let me discharge it.
