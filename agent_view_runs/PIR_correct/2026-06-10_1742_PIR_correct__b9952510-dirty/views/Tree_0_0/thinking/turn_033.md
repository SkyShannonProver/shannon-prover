# Tree-0.0 · turn 33 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:56:29.400Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /predT in H; smt(big_cons xorwA xorwC xorw0 xorwK).`

---

The explicit `big_cons` rewrite no-ops (and aborts the chain). Let me instead unify `predT` in `H` and pass `big_cons` as an `smt` hint so smt does the beta-reduction itself.
