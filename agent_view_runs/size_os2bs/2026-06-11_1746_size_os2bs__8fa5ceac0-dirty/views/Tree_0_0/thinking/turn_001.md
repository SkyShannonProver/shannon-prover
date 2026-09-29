# Tree-0.0 · turn 1 · commit_tactic

<!-- session 576385c6-1557-42f8-ae01-14016b4cb3f3 · 2026-06-12T00:46:46.018Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite /os2bs size_map size_chunk.`

---

I'll start by loading the proof intent tool and reading the current workspace view.

The goal is `size (os2bs os) = size os %/ 16`. Let me check the definition of `os2bs` in the source file before choosing a tactic.

`os2bs os = map mkblock (chunk 16 os)`, so the goal follows from `size_map` and `size_chunk` (with the trivial side condition `0 < 16`). Submitting that as one tactic.
