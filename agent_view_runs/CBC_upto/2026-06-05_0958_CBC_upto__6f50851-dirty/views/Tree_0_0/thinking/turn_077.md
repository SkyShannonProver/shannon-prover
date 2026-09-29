# Tree-0.0 · turn 77 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:43:30.113Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 2 2: (={i, s, c, p, x, DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1} /\ !DoubleQuery.bad{2} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2} /\ i{1} < size p{1} /\ i{2} < size p{2}).`

---

**Case 2: `!bad{2}`** (so `!bad{1}`). Peel `pi`/`x`, keeping `={x}`, `fdom m=qs`, and bad-equality.
