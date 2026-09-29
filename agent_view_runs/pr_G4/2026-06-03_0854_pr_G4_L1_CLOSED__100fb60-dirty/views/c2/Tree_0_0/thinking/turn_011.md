# Tree-0.0 · turn 11 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:00:52.201Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; auto; smt(size_cons size_ge0).`

---

Now the oracle obligation `hoare[G4.O.dec : J ==> J]`. The body is deterministic (assignments + an `if`); `proc; auto` computes the wp, leaving size arithmetic over `ci :: log` / `ci :: cilog`, closed by smt with the cons-size and nonnegativity facts.
