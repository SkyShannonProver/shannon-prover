# Tree-0.1 · turn 35 · commit_tactic

<!-- session dbe52ca4-5aee-47b2-86f1-a4030a610470 · 2026-07-09T04:00:23.364Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite xorwC !big_cat big_consT; move: (big predT<:int> a u1) (big predT<:int> a u2) => A B; rewrite (xorwC (a i0) B) !xorwA.`

---

Goal 2 is the symmetric disjunct — same identity with the two sums swapped. Let me swap with `xorwC` and run the same normalization.
