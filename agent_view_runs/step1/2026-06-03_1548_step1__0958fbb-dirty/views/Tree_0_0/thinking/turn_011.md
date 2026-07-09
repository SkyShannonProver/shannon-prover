# Tree-0.0 · turn 11 · undo_last_step

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:57:37.689Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

Confirmed: `pr_CCP_OCCP: ∀ (I<:Init) (A0(S:SKE)<:Adv) &m, Pr[A0(GenChaChaPoly(OCC(I))).main()] = Pr[A0(OChaChaPoly(I)).main()]`. The section has `local module G1(S) = CCA_game(A, RealOrcls(S))` — exactly the wrapper functor `A0`. So `pr_CCP_OCCP I_stateless G1 &m` bridges my Pr term. 

Per the advisor, I'll undo the `byequiv` to do this rewrite at Pr level. Undoing now.
