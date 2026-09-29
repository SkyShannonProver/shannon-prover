# Tree-0.0 · turn 24 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:49:40.841Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline {2} 1.`

---

Let me read the current workspace view to recover the exact proof state.

Let me check my proof history and the source to understand the structure.

Let me read the source lemma and relevant definitions.

Let me read the UFCMA and UFCMA_poly module definitions.

This is the hard UFCMA reduction goal: `UFCMA(A,St).main ~ UFCMA_poly(A,FinRO).main` with post `(exists c forgery){1} => forged{2}`. Key tool is `UFCMA_genCC`. Let me expose the RHS body by inlining.
