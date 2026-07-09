# Tree-0.0 · turn 2 · commit_tactic

<!-- session c21b3c11-4299-4bea-80ed-568d8fded3e3 · 2026-06-12T00:53:20.022Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite /mkseq /= (iotaS _ 0) //= drop0 -(size_tag t) take_size mktagK.`

---

First step accepted — the chunk count reduced to 1. Now expanding `mkseq`/`iota` and closing with `take_size` + `mktagK`, following the `os2tK` template.
