# Tree-0.0 · turn 18 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:07:00.935Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true); auto.`

---

Post is `true`, bound `≤ 1`. Now discharge: peel the `A.guess` call with the trivial-invariant adversary form (same idiom as the prefix, which set up `ll_dec` for losslessness), then `auto` for the head assignments.
