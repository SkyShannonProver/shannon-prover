# Tree-0.1 · turn 1 · commit_tactic

<!-- session d797208c-0e04-411f-86cd-c693f160a1a7 · 2026-06-12T00:28:51.524Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> /offunE ->.`

---

I'll start by reading the latest workspace view to see the current proof state.

The sibling lemma `andbE` (line 85-86) has the exact same shape and is proved with `by move=> /offunE ->.`. Since `(+^)` is also defined via `Block.offun`, the same proof should work for `xorbE`.
