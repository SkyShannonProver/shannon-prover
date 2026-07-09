# Tree-0.0 · turn 21 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:23:20.001Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (: _ ==> ((g ^ G1.u, G1.g_ ^ G1.u', g ^ r', g ^ r) \in G3.cilog) /\ size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) (: _ ==> size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w).`

---

The `conseq` collapsed back to `post = tuple∈cilog` because I gave the bd-judgment post as just `tuple`. I need the **bd-judgment post to be the enriched conjunction** `tuple ∧ FACTS`, with the hoare judgment supplying `FACTS` (so total-probability gives the original). Let me redo it correctly.
