# Tree-0.0 · turn 31 · commit_tactic

<!-- session 354e64c4-4674-4b25-b8c4-d27693ff67ca · 2026-06-03T17:16:06.146Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ! ((G3.a, G3.a_, G3.c, G3.d) \in G3.cilog) /\ G1.cstar <> None).`

---

Reduced to `hoare[tail : !R ==> !R]`. Carry invariant `!R ∧ cstar≠None` through the call (O.dec leaves cilog untouched when cstar≠None).
