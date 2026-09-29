# Tree-0.1 · turn 1 · commit_tactic

<!-- session 66372df5-7f4c-455e-92d6-975e7d4c71cc · 2026-06-09T03:15:34.502Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc (={glob I, glob OCC}).`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the latest followup and manager result for more context.

This is a fresh node proving `CCP_OCCP`, an equiv between `A(GenChaChaPoly(OCC(I))).main` and `A(OChaChaPoly(I)).main`. Let me read the source file.

Let me read the relevant section of the source file in detail.

Let me look at the `SKE` and `FCC` module types and the adversary structure.

Let me check the SKE module type definition.

I now understand the structure. `CCP_OCCP` proves two SKE implementations equivalent under abstract adversary `A`: `GenChaChaPoly(OCC(I))` (procedural ChaCha/Poly loops) vs `OChaChaPoly(I)` (operator form). The bridge is the `chacha_spec` and `poly_spec` phoare lemmas declared just above. SKE has procedures init/kg/enc/dec, so the standard approach is `proc (={glob I, glob OCC})`.

Let me start the proof.

I'll commit the opening tactic for the abstract adversary equivalence.
