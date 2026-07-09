# Tree-0.0 · turn 1 · commit_tactic

<!-- session 37ac3f64-40de-4b72-bc6c-adc7bc442ee5 · 2026-06-12T00:51:02.862Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite /t2os size_tag.`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is `size (t2os t) = 32` with `t: tag`. Let me check the source file for the `t2os` definition.

`t2os t = oftag t`, and sibling proofs use a `size_tag` lemma (line 187). The proof should be a one-liner. Submitting it.
