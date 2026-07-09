# Tree-0.1 · turn 7 · commit_tactic

<!-- session 8c9ef070-9d41-4ff7-8efe-17ac8095a336 · 2026-06-09T02:59:38.839Z -->

**Intent:** `commit_tactic`  
**Payload:** `split; last by smt(size_drop size_eq0 size_ge0).`

---

The oget simplified to `r0L`. Now I need the size lemma for `bytes_of_block`. Let me check its name.

`bytes_of_blockP` is the subtype size lemma (qualified `Block.bytes_of_blockP`). Let me peel off the two `drop`-empty implications first.
