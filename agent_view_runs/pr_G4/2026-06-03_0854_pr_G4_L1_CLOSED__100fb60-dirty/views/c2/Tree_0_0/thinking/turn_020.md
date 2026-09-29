# Tree-0.0 · turn 20 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:09:22.948Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ll_dec2 : islossless G4.O.dec by islossless.`

---

`call (_: true)` is the losslessness-preservation form for `= 1%r` branches (as used in the prefix), but this branch is `≤ 1%r`. I need to supply A.guess's losslessness explicitly. First establish the oracle is lossless (fresh name to avoid clashing with the prefix's `ll_dec`).
