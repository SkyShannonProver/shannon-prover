# Tree-0.1 · turn 1 · commit_tactic

<!-- session 86f7e591-365e-4bdd-9a5c-4f0bde8d4a0b · 2026-06-12T00:29:58.200Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b; apply/blockP=> i ge0_gti_n; rewrite xorbE // offunE // xorw0.`

---

I'll read the current workspace view to see the proof state.

The goal is `right_id zerob (+^)`. Let me check the source file for the relevant definitions.

Sibling lemmas (xorbC, xorbK) use the `blockP` + `xorbE` pattern. Let me check the surrounding context briefly.

The proof pattern is clear from siblings: `blockP` + `xorbE` + `offunE` + word-level `xorw0`. I'll commit it.
