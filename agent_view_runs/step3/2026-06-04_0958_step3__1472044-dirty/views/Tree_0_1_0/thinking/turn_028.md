# Tree-0.1.0 · turn 28 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:38:45.951Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; rnd{1}; wp; skip.`

---

The `rnd` coupling applied cleanly (the measure obligation auto-discharged via the `dpoly_out` funiform/full hints). The two inverse obligations are exactly `poly_out_sub_add` and `poly_out_add_sub`. Now process the remaining left-only `r5` sample and reduce to a pure goal: absorb `13–15`, consume `r5` (lossless `dpoly_in`), absorb `1–11`, then `skip`.
