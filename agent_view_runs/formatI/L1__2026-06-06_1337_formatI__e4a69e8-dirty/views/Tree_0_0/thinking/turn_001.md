# Tree-0.0 · turn 1 · commit_tactic

<!-- session 7507390e-3397-450f-af34-e9dbd0b6cf44 · 2026-06-06T20:37:44.117Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> h.`

---

I'll start by reading the current workspace view to understand the proof state.

Let me look at the source file to understand the `formatI` lemma and surrounding definitions.

Let me find the `formatI` lemma definition and the `(||)` operator.

I understand the goal. `formatI` says `(||)` is injective: from `(r || p) = (r' || p')` prove `(r,p) = (r',p')`. There's a sibling lemma `parseK : parse (r || p) = (r,p)` — so applying `parse` to both sides gives the result.

Let me load the MCP tool and start the proof.

I'll commit the introduction of the hypothesis first.
