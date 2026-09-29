# Tree-0.0 · turn 10 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:00:29.457Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: size G3.cilog <= PKE_.qD /\ size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD).`

---

`conseq` cleaned the post and auto-discharged the entailment. Now handle the `A.choose` call. The oracle `O.dec` only appends to `cilog`/`log` under the `size log < qD` guard, so the inductive invariant is `size cilog ≤ size log ≤ qD` (which yields `size cilog ≤ qD`). `w` and `g_` are framed (A can't write G1 globals).
