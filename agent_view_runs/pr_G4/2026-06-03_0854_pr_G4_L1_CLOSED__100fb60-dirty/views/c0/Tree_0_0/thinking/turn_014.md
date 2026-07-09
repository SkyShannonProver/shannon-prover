# Tree-0.0 · turn 14 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:11:04.971Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 13 : (size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.`

---

Back at the main bound. Now redo the cut carrying `G1.w <> zero` and `G1.g_ = g ^ G1.w`.
