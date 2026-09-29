# Tree-0.1 · turn 44 · probe_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:42:09.783Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto => /=; rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_setE mem_set).`

---

Left is now just a deterministic prefix. Let me try to close the whole tail with `auto` + unfolds + the algebraic lemmas.
