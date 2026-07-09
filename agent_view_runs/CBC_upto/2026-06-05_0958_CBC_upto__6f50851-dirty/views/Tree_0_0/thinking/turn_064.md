# Tree-0.0 · turn 64 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:41:05.212Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={i, p} /\ DoubleQuery.bad{1} = DoubleQuery.bad{2} /\ (!DoubleQuery.bad{2} => ={s, c, DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).`

---

Apply the while invariant with `bad{1}=bad{2}` lifted out of the implication.
