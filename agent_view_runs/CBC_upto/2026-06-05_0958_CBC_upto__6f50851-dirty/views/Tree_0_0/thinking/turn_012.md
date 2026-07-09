# Tree-0.0 · turn 12 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:15:43.728Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={i, p} /\ (!DoubleQuery.bad{2} => ={s, c, DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1})).`

---

Now apply the loop invariant (`fdom` kept *inside* the `!bad{2}` implication per the advisor).
