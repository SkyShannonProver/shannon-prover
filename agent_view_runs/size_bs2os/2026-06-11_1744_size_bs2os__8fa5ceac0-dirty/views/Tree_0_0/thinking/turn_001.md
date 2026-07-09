# Tree-0.0 · turn 1 · commit_tactic

<!-- session 4810055b-0bed-417d-bc37-0a7cb958487e · 2026-06-12T00:45:31.827Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /bs2os; elim: bs => [|b bs ih] //=.`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is `size (bs2os bs) = 16 * size bs`. Let me check the definition of `bs2os` in the source file.

`bs2os bs = flatten (map ofblock bs)`. Let me verify the `size_block` lemma and load the proof intent tool.
