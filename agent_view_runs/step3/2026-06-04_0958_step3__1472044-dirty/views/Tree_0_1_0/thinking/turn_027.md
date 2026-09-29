# Tree-0.1.0 · turn 27 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:38:17.426Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd (fun (z : poly_out) => z + poly1305_eval r10{1} (topol a0{1} c3{1})) (fun (z : poly_out) => z - poly1305_eval r10{1} (topol a0{1} c3{1})).`

---

Frontier is now at the `r6 ~ t` sampling. The tag is `poly1305 r10 r6 (topol a0 c3) = r6 + poly1305_eval r10 (topol a0 c3)`. Couple `r6{1}` with `t{2}` via the bijection `z ↦ z + poly1305_eval r10 (topol a0 c3)` (offset `+c`, inverse `-c`), valid since `dpoly_out` is funiform/full.
