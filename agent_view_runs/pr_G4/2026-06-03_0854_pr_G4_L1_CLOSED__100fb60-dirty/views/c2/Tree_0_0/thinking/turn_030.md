# Tree-0.0 · turn 30 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:15:55.424Z -->

**Intent:** `commit_tactic`  
**Payload:** `hoare.`

---

Remaining 2 — the `!R ==> R` branch, bound `[<=] 0%r`. Key insight: statement (3) sets `cstar = Some(challenge)`, so during `A.guess` the oracle's `cilog` update `(cstar=None)? ci::cilog : cilog` leaves `cilog` **unchanged** (cstar≠None). So if the tuple wasn't in `cilog` before, it can't appear — post is impossible. Reduce to hoare and carry the invariant `!R ∧ cstar≠None` through the call.
