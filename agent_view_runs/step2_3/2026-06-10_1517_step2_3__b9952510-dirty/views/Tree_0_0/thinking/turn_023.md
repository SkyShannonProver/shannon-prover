# Tree-0.0 · turn 23 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:47:56.447Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll. have hC := pr_RO_FinRO_D h_dout (G5(A)) &m () (fun (r:bool) => r); rewrite /= in hC; rewrite -hC.`

---

Let me check the exact signature of `pr_RO_FinRO_D`.

Let me check the PROM section header to get the exact declared-argument order for `pr_RO_FinRO_D`.

The hypotheses `h_dout` etc. lived in subgoal 1's branch (introduced after `congr`); subgoal 2 doesn't have them. Re-establishing `h_dout`, then the FinRO bridge.
