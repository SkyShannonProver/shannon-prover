# Tree-0.0 · turn 19 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:42:21.802Z -->

**Intent:** `commit_tactic`  
**Payload:** `skip => &hr [[hu hsz hw hg] _]; split; last by move=> _ v _ h; exact h.`

---

Same shape. `skip`, intro (now `hu` is the carried first-coordinate fact), split, and discharge the trivial conjunct (`X => Y`, so a leading `_`).
