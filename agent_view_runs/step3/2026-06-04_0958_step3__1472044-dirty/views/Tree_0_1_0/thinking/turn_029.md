# Tree-0.1.0 · turn 29 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:40:04.273Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2; rewrite /inv_cpa /poly1305 /=; smt(mk_rs_ofpair get_set_sameE get_setE mem_set domE poly_out_sub_add poly_out_add_sub).`

---

Now a pure logical goal. Everything is derivable: the two inverse obligations are `poly_out_sub_add`/`poly_out_add_sub`; `tpl` simplifies via `mk_rs_ofpair` to `(r10, r6L)`, making `c0_L`'s tag `= r6L + poly1305_eval r10 ... = t_R`; the `lenc` equality now holds via `p{1}=p{2}`; freshness from the unfolded `inv_cpa` + `mem_set`. Unfold the opaque ops and discharge with smt given the algebraic/map lemmas.
