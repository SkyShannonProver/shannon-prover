# Tree-0.0 · turn 10 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:15:28.541Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 3 3: (={i, s, c, p} /\ !DoubleQuery.bad{2} /\ ={DoubleQuery.qs} /\ fdom PRFi.m{1} = DoubleQuery.qs{1}).`

---

I now have the enc body. This is the asymmetric upto-bad loop (the crux). Let me lay out my plan and get the advisor's read before grinding through the body, since this profile has no probe (every step mutates state).

My plan:
- `seq 3 3: (={i,s,c,p} /\ !bad{2} /\ ={qs} /\ fdom m{1}=qs{1})` — prefix couples `s<$dBlock` by identity; close with `auto`.
- `while (={i,p} /\ (!DoubleQuery.bad{2} => ={s,c,DoubleQuery.qs} /\ fdom PRFi.m{1}=DoubleQuery.qs{1}))`.
- Body: inline the `f` calls, then `case (DoubleQuery.bad{2})` — when bad, implication vacuous, samples independent (lossless); when `!bad`, sub-case on `mem qs x` (x∉qs ⇒ both sample fresh, identity couple; x∈qs ⇒ bad flips, asymmetric `rnd{2}`).

Note I did *not* put `bad{1}` in the call invariant — but `bad` is a pure observer flag (PRFi.f/Sample.f dynamics depend only on the map/qs), so it's not needed.

Solid guidance. Let me set up the prefix split.
