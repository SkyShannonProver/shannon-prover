# Tree-0.0 · turn 32 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:48:51.806Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 : (g ^ G1.u \in map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog /\ G1.g_ ^ G1.u' \in map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog /\ g ^ r' \in map (fun (t : PKE_.ciphertext) => t.`3) G3.cilog /\ size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) (PKE_.qD%r / order%r) (PKE_.qD%r / order%r) 1%r 0%r.`

---

`u'` factor done. Now peel `r'` (base `g`, distribution `dt`, factor `qD/order`).
