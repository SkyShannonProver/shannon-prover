# Tree-0.0 · turn 15 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:19:16.065Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_: _ ==> DoubleQuery.bad{2} /\ i{1} = i{2} /\ p{1} = p{2}).`

---

**Case 1: `bad{2}` true (vacuous implication).** I'll weaken the post to just `bad{2} /\ ={i,p}` since the implication is vacuous, then discharge the samples by losslessness.
