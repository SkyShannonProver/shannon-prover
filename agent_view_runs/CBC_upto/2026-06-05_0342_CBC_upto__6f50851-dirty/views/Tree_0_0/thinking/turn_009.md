# Tree-0.0 · turn 9 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T10:48:16.682Z -->

**Intent:** `probe_tactic`  
**Payload:** `byequiv (_: ={glob A} ==> ={DoubleQuery.bad} /\ (!DoubleQuery.bad{2} => ={res})).`

---

The byequiv forms shown cover `=` and `<=`, but our goal is the abs-difference upto-bad form `|Pr1 - Pr2| <= Pr[bad]`. EasyCrypt's `byequiv` supports this via the Fundamental Lemma when the post has shape `={bad} /\ (!bad => ={res})`. Let me probe that form.
