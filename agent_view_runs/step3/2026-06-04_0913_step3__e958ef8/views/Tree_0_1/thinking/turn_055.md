# Tree-0.1 · turn 55 · probe_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:50:16.092Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /= !get_set_sameE /= !mk_rs_ofpair /= /poly1305 /inv_cpa /=; smt(poly_out_sub_add poly_out_add_sub mem_set).`

---

Now the ambient goal has `p.\`1 = n`. Let me reduce the map lookups + `mk_rs_ofpair` + unfold, then smt.
