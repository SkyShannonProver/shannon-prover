# Tree-0.0 · turn 16 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:40:48.113Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 : (g ^ G1.u \in map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog /\ G1.g_ ^ G1.u' \in map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog /\ size G3.cilog <= PKE_.qD /\ G1.w <> zero /\ G1.g_ = g ^ G1.w) (PKE_.qD%r / (order - 1)%r) ((PKE_.qD%r / order%r) ^ 2) 1%r 0%r.`

---

First peel complete. Now the continuation `phoare[ u'; r'; r : (g^u∈L1 /\ statics) ==> post ] <= (qD/order)^2·(qD/(order-1))`. Peel `u'` (factor `qD/(order-1)`, distribution `dt \ pred1 u`).
