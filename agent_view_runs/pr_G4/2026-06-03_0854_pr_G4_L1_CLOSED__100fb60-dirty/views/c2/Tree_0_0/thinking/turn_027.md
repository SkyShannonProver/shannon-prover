# Tree-0.0 · turn 27 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:15:07.050Z -->

**Intent:** `commit_tactic`  
**Payload:** `conseq (_: _ ==> true : =1%r).`

---

The blocker is the `[<=] 1%r` comparison: the abstract-adversary `call` only proves `= 1%r` (losslessness), which EC won't fit into a `≤` goal. I need to strengthen the goal's bound to `= 1%r`. Let me find the correct conseq-bound syntax from existing EC sources.

Found the syntax: `conseq (_: ... : =1%r)`. Strengthen the goal's bound to `=1%r` (losslessness), which implies the `≤1` goal — then the abstract-adversary `call (_: true)` will fit.
