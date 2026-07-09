# Tree-0.0 · turn 72 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:40:37.061Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0).`

---

The `exists*`/`elim*` + `call (f_eqM B0)` approach is accepted. Let me verify it closes the loop body (remaining → 4).

remaining → 4: the loop body is closed (monotonicity resolved). Committing.
