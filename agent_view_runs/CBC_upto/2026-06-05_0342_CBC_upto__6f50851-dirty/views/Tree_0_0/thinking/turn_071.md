# Tree-0.0 · turn 71 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:40:26.573Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0).`

---

`call (f_eqM DoubleQuery.bad{2})` — the `{2}`-annotated term isn't valid as a proof-term arg. The idiom is to capture the pre-call `bad{2}` as a logical var via `exists*`/`elim*`, then pass it. Probing.
