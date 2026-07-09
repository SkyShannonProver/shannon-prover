# Tree-0.0 · turn 1 · probe_tactic

<!-- session a2de5c6f-e04f-4d2b-ab6e-ef29b7562b99 · 2026-06-03T18:21:07.632Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> *; smt(neq_w1_w2 nth_out_of_range).`

---

I'll start by analyzing the current goal. This is a pure ambient tail — the postcondition obligation from the `call` for the abstract adversary. Let me reason about it before probing.

The goal: given the invariant (which includes `lbad1_L = lbad1_R`), prove the implication `(let tt = nth (w1,w2) lbad1_L nth0 in tt.1 = tt.2) => badi_R`, where `badi_R = (nth0 < size lbad1_R /\ entry-equal)`.

Key insight: the equality part transfers via `lbad1_L = lbad1_R`. The `nth0 < size` part comes from `neq_w1_w2`: if `nth0 >= size`, `nth (w1,w2) lbad1 nth0 = (w1,w2)`, so `tt.1 = w1 <> w2 = tt.2`, contradicting the antecedent. Let me probe a closing tactic using that axiom.
