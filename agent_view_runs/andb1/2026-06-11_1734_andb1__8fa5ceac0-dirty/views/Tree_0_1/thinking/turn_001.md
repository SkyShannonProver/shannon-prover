# Tree-0.1 · turn 1 · commit_tactic

<!-- session 65913e20-514f-4f24-858d-e0be579f4092 · 2026-06-12T00:35:40.217Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b; apply/blockP=> i ge0_gti_n; rewrite !andbE 2:offunE // andw1.`

---

I'll start by reading the latest workspace view to see the current goal state.

The structure mirrors `xorb0` exactly. I'll commit the analogous tactic, using `andw1` for the per-word identity.
