# Tree-0.0 · turn 6 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:46:06.065Z -->

**Intent:** `probe_tactic`  
**Payload:** `have ->: Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] = Pr[MainD(G4(A), FinRO).distinguish() @ &m : res].`

---

I'm on subgoal 1: `Pr[CPA_game(...CCRO(FinRO))] = Pr[Split1.MainD(G8(A), RO_Pair(I1,I2))]`. Having read SplitRO, I've derived a multi-layer ladder (peel SplitC2 → SplitC1 → SplitDom codomain/domain splits via `pr_RO_split`, bridge clone-instance and FinRO/RO mismatches, then a final `byequiv` to the CPA game). Let me get the advisor's read on this ladder and the clone-mismatch concern before committing many turns.

Advisor confirms the ladder and says spike the LHS-forward bridge first. Let me start with the manager's confirmed anchor — probe the `have ->` rewriting the CPA term to `MainD(G4, FinRO)` form to confirm names typecheck.
