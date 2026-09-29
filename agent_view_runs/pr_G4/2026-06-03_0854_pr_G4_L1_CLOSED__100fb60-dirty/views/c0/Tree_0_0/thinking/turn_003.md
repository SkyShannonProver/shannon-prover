# Tree-0.0 · turn 3 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T15:59:59.174Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 1%r 1%r 0%r.`

---

EC now shows the program with the postcondition decided after statement 21 (statements 22–25 don't affect `G3.a..d` or `G3.cilog`). Let me split off the trailing adversary call. I'll bound the first 21 statements by the full bound, and show the tail preserves the event.
