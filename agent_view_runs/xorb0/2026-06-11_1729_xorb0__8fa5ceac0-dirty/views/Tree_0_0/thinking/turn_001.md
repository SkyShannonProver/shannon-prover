# Tree-0.0 · turn 1 · commit_tactic

<!-- session f4b6d66c-08e1-4fc3-8ddd-6a30df4c966d · 2026-06-12T00:29:53.214Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b; apply/blockP=> i ge0_gti_n; rewrite xorbE // offunE // xorw0.`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is `right_id zerob (+^)`. Let me check the source file for the relevant definitions.
