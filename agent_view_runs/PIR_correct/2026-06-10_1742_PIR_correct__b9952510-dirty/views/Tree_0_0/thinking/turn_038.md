# Tree-0.0 · turn 38 · lookup_symbol

<!-- session 61c51f31-dc55-4d83-a89a-cd3ee77df49c · 2026-06-11T01:03:33.455Z -->

**Intent:** `lookup_symbol`  
**Payload:** `BBS.big_cons`

---

The probe classification is confusing — a failing smt should error, not report "no change." Let me read the raw manager result for ground truth on what actually happened.

311ms is too fast for a real smt search — the `rewrite /predT in H` half may be erroring and getting mislabeled. Let me look at the actual proof context in the source file to see how this invariant is meant to close and what lemmas exist.

Let me get the exact statement of `big_cons` to confirm it even matches the goal's `big` form.
