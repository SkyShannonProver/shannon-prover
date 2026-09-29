# Tree-0.0 · turn 19 · probe_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:32:31.521Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &1 &2 [_ ->] /=; smt().`

---

Now close the pure residual: intro, substitute `i0=nth0`, simplify (reduces `size []`, `nth _ []`), then `smt` with `H` for `nth0 < 0` being false. Let me probe.
