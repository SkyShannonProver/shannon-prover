# Tree-0.0 · turn 19 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:01:10.914Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{2} D(A, IndBlock).guess.`

---

After inlining: RHS is `IndBlock.init(); D.O.init(); b0 <@ A(D.O).main(); b <- b0`. LHS is `RealOrcls(...).init(); b <@ A(...).main()`. Committing the inline, then I'll build the call-invariant.
