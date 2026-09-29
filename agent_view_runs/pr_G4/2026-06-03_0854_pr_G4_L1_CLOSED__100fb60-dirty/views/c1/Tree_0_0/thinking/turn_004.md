# Tree-0.0 · turn 4 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:29:44.917Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 : (g ^ G1.u \in map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog /\ size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) (PKE_.qD%r / order%r) ((PKE_.qD%r / order%r) ^ 2 * (PKE_.qD%r / (order - 1)%r)) 1%r 0%r.`

---

The implication is discharged; now I'm back at the main `phoare` with the weakened (4-projection) post. Now I peel the first sample `u` with a multiplicative `seq`. Strategy per peel: cut on "this coordinate ∈ its projection list" with probability `p1`, continuation `p2`, and the `!R` branch contributes 0 (since post requires this membership). Let me peel `u`.
