# Tree-0.1 · turn 1 · commit_tactic

<!-- session fba3c86e-236e-46ee-a0ab-897329dc773a · 2026-06-12T00:33:27.800Z -->

**Intent:** `commit_tactic`  
**Payload:** `by apply/blockP=> i ge0_gti_n; rewrite xorbE // offunE // xorwK.`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is `b +^ b = zerob` — XOR self-cancellation on blocks. Let me check the source file to see how `block`, `+^`, and `zerob` are defined.
