# Tree-0.0 · turn 15 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:38:37.399Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> _ v _ h; exact h.`

---

The `mu` bound is proved; this remaining goal is the trivial coverage conjunct `(bound) => forall v, ... => Q v => Q v`. Discharge it.
