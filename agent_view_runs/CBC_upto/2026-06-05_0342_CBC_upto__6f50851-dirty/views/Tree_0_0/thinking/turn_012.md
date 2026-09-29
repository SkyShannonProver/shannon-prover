# Tree-0.0 · turn 12 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:50:55.193Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2} => ={res})) => //.`

---

Two identical fast failures with "invalid goal shape" — and the manager explicitly says this is "not proof that the tactic is invalid," with timing (534ms) too fast to have reached EC. This looks like the probe-layer shape pre-filter rejecting the abs-difference form, not EC itself. The abs-diff upto-bad form is the canonical switching-lemma endgame, and `commit_tactic` reaches EC directly (and is reversible via undo). Let me commit it to get EC's ground truth.
