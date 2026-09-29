# Tree-0.0 · turn 1 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:27:45.209Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (: _ ==> (g ^ G1.u \in map (fun (t : ciphertext) => t.`1) G3.cilog) /\ (G1.g_ ^ G1.u' \in map (fun (t : ciphertext) => t.`2) G3.cilog) /\ (g ^ r' \in map (fun (t : ciphertext) => t.`3) G3.cilog) /\ (g ^ r \in map (fun (t : ciphertext) => t.`4) G3.cilog) /\ size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w).`

---

I'll start by loading the proof-intent tool, then read the current state carefully before committing.

I have the full handoff goal. Let me reason about the proof before acting.

The goal is a `phoare` upper bound: after sampling `u, u', r', r`, the probability that the fresh tuple `(g^u, g_^u', g^r', g^r)` lands in the fixed list `G3.cilog` (size ≤ qD) is `≤ (qD/order)^3 · (qD/(order-1))`.

Key insight: `tuple ∈ cilog ⟹` each coordinate is in the corresponding projection list, and the four samples are independent. So I'll first **weaken the post** to a conjunction of four independent projection-membership events (valid since `tuple∈L ⟹ ∧ proj_i`), then peel each sample with a multiplicative `seq` to get one factor each.

Let me start with the `conseq` weakening.
