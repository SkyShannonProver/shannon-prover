# Tree-0.0 · turn 58 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:23:46.732Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp 1 1; wp; call f_eq; auto; smt(size_ge0).`

---

Let me check whether `sp 1 1; wp; call f_eq; auto` closes the body or leaves a residual.

`sp 1 1; wp; call f_eq; auto` leaves a pure-logic residual (f_eq's pre from the invariant + reconstructing the invariant after the updates) — closable by smt. Probing with smt appended.
