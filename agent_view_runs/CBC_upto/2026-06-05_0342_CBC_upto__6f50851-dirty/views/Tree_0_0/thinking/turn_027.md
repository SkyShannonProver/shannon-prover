# Tree-0.0 · turn 27 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:09:18.966Z -->

**Intent:** `probe_tactic`  
**Payload:** `conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}).`

---

Now the `bad{2}`-true branch: bodies diverge but both are lossless and `bad` is monotone, so I only need `bad{1}<=>bad{2}` (both stay true). Let me weaken the post to `bad{1} /\ bad{2}` via `conseq` and see the resulting goals.
