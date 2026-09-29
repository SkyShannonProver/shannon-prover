# Tree-0.0 · turn 28 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:09:38.933Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_: _ ==> DoubleQuery.bad{1} /\ DoubleQuery.bad{2}); first by smt().`

---

The conseq yields (1) a trivial post-implication side goal (`bad_L/\bad_R => ...`) and (2) the equiv with simplified post `bad{1}/\bad{2}`. Let me commit the conseq and discharge the trivial side goal with smt.
