# Tree-0.0 · turn 15 · commit_tactic

<!-- session d09e7b01-d19a-40f9-88c6-39b890db65fb · 2026-07-09T03:56:06.500Z -->

**Intent:** `commit_tactic`  
**Payload:** `move => _ v _; case: Hinv => Hi Hr Hjb Hss Hsx; rewrite Hi /predT /=.`

---

Now the invariant-preservation goal for all `v`. Let me intro, destruct the invariant, and rewrite `i{hr}=i0`.
