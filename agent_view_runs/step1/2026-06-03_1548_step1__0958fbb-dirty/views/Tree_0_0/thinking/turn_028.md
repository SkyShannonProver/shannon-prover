# Tree-0.0 · turn 28 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:05:01.865Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; call (_: Mem.k{1} = IndBlock.k{2}).`

---

Let me see what subgoals the `call` produces.

The `call` produces the enc/dec oracle obligations (remaining 2→4: enc, dec, plus the congr subgoal-2 and likely the main residual). First obligation is `RealOrcls(GenChaChaPoly(OCC(I_stateless))).enc ~ D.O.enc`. Committing the call.
