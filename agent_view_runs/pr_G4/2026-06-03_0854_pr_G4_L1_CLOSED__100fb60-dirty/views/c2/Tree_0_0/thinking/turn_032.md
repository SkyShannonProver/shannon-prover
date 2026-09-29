# Tree-0.0 · turn 32 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:16:18.225Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; auto; smt().`

---

Oracle obligation `hoare[G4.O.dec : I ==> I]`. With `cstar≠None`, the `cilog` update reduces to a no-op, so membership is preserved — `proc; auto; smt()` handles the conditional.
