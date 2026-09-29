# Tree-0.0 · turn 47 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:19:55.726Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto; smt(fdom_set get_set_sameE).`

---

Core sampling-coupling goal: couple `r0` on both sides, then maintain `={r}`, `={qs}`, and `fdom (m.[x<-r0]){1} = qs∪{x}`. Probing with `auto` (couples the sample) plus `fdom_set`/`get_set_sameE`.
