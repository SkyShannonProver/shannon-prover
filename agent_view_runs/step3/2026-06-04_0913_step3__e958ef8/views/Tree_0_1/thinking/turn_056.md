# Tree-0.1 · turn 56 · probe_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:51:15.693Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite /poly1305 /inv_cpa /=; smt(mk_rs_ofpair poly_out_sub_add poly_out_add_sub get_set_sameE oget_some mem_set).`

---

The lemma rewrites can't reach under the binders. Let me unfold (delta works under binders) and hand smt the map/algebra lemmas directly.
