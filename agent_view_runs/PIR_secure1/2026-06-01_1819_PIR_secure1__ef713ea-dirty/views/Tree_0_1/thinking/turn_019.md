# Tree-0.1 · turn 19 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:31:19.161Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &1 &2 a -> ->.`

---

Good, `bypr` committed. The first subgoal is:
```
forall &1 &2 (a : int list),
  PIR.s{1} = a => PIR.s{2} = a => PIR.s{1} = PIR.s{2}
```

This is trivially `smt()` or `by move=> &1 &2 a -> ->`. Let me close it quickly.
