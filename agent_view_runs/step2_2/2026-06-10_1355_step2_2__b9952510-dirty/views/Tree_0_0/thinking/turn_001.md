# Tree-0.0 · turn 1 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T20:58:34.225Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h1 : Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] = Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res].`

---

I'll start by reading the current workspace view to understand the proof state.

Let me check the latest followup and the source file to understand the lemma context.

Let me read the source file to understand the lemma and its surrounding context.

The goal is a sum-of-probabilities inequality. Let me look at the available sibling lemmas/equivs in this section to find the building blocks.

Let me read the key module definitions: `UFCMA_poly`, `CCRO`, and look for `UFCMA` and `St`.

`UFCMA_poly` wraps the same `CPA_game(...GenChaChaPoly(CCRO(FinRO)))` that appears in RHS_a, then computes a forge event. Let me find `StLSke`, `UFCMA`, and any equiv relating the two CPA games.

`UFCMA(A,St)` is definitionally `CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St)))`, so LHS_a and LHS_b are the same program with different events. Let me read the SKE framework definitions.

This confirms the structure. `UFCMA(A,St)` is literally `CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St)))`, so:
- LHS_a = RHS_a via `UFCMA_genCC` (the `res` event),
- LHS_b ≤ RHS_b is the real forgery bound.

Let me start the proof by introducing the equality `h1` for the first terms.

I'll commit the first equality (LHS_a = RHS_a) via `UFCMA_genCC`.
