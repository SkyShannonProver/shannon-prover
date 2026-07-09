# Tree-0.0 · turn 22 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:10:32.942Z -->

**Intent:** `commit_tactic`  
**Payload:** `have Hg : islossless G4.A.guess by apply (guess_ll G4.O ll_dec2).`

---

The explicit `call (lemma)` was rejected — let me isolate whether it's the `guess_ll` application or the call tactic by first proving A.guess losslessness as a hypothesis.
