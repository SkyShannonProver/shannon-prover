# Tree-0.0 · turn 67 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:41:30.198Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}).`

---

**Case 1: `bad{2}` true** (so `bad{1}` true via invariant). Weaken post to track both bad flags + `={i,p}`.
