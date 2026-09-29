# Tree-0.1 · turn 4 · commit_tactic

<!-- session a7472aaf-be97-4058-b42c-c8c823c1a2a1 · 2026-06-09T00:00:40.293Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res].`

---

Now I understand the top-level structure. The proof is: rewrite the LHS `Pr` via a game equivalence (`OChaChaPoly(IFinRO)` ≡ `StLSke(St)`, since both compute enc/dec via the same operators on the same RO-map state), then `apply CCA_UFCMA.CCA_CPA_UFCMA St _ _ A A_ll &m`. Let me read the game/oracle definitions to nail the equiv invariant.

I now have the full picture. The proof is a top-level bridge: rewrite the LHS `Pr` to the `StLSke(St)` form (the two CCA games are observationally equal — `OChaChaPoly(IFinRO)` computes enc/dec via the same operators that the `CCA_UFCMA` clone gave `StLSke`), then apply the generic lemma. Let me commit the bridging `have ->`.
