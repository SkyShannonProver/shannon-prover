# Tree-0.1 · turn 3 · lookup_symbol

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-08T23:58:08.340Z -->

**Intent:** `lookup_symbol`  
**Payload:** `CCA_UFCMA.CCA_CPA_UFCMA`

---

The generic CCA→CPA+UFCMA theorem lives in the cloned `CCA_CPA_UFCMA` theory (from `Ske`). Let me find that source to identify the generic lemma I can apply.

This is the key finding: the generic `CCA_CPA_UFCMA` lemma (ske.ec:186) is *exactly* my goal, except its LHS is `CCA_game(A, RealOrcls(StLSke(St)))` while mine is `CCA_game(A, RealOrcls(OChaChaPoly(IFinRO)))`. So the proof is: bridge the two CCA games by a `Pr` equality, then apply the cloned generic lemma. Let me get the generic lemma's exact instantiated signature.
