# Tree-0.0 · turn 4 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:21:14.060Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob A} /\ arg{2} = nth0 ==> (let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) => UFCMA_li.badi{2}).`

---

The byequiv probe was accepted as a structural transition. Let me read the full view to see what the post-probe goal looks like.

The `byequiv` leaves 3 subgoals (the equiv judgment plus two side conditions). Let me commit it.
