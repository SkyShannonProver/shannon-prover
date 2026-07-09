# Tree-0.1 · turn 12 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:02:34.757Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &2; rewrite /enc /get /=.`

---

The two sides differ only in `enc`/`get` being folded vs unfolded; substitution already aligned `cc gs` to `oget gs.[n,c]`. Let me unfold `enc` and `get` to close.
