# Tree-0.0 · turn 70 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:39:58.527Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp 1 1; wp; call (f_eqM DoubleQuery.bad{2}); auto; smt(size_ge0).`

---

`f_eqM` is proven and in context. Now redo the loop body with `call (f_eqM DoubleQuery.bad{2})` (instantiating `B` with the pre-call `bad{2}`, giving monotonicity), then close with smt. Probing.
