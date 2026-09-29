# Tree-0.0 · turn 22 · commit_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:35:17.697Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Goal 1 closed. Now goal 2 is the adversary-call part: pre is the invariant, code is `b2<@A.main(); b1<-b2; b0<-b1; b<-b0` on both sides, post is the event implication. Let me absorb the trailing assigns with `wp`.
