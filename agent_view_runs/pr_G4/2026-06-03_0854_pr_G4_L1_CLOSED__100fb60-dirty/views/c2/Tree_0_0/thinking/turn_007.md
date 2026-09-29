# Tree-0.0 · turn 7 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T16:58:33.901Z -->

**Intent:** `commit_tactic`  
**Payload:** `hoare.`

---

Remaining 5 — this is the "fail branch" of the outer `seq 13` split (bound `[<=] 0%r`, pre `true`, post `!(invariant)`). It says: the probability that the prefix *fails* to establish `size cilog ≤ qD ∧ w≠0 ∧ g_=g^w` is 0. Reduce to a hoare judgment proving the invariant always holds.
