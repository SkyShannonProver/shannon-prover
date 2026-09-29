# Tree-0.1.1 · turn 17 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:43:09.776Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m0; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap).`

---

Side goal: prove `x4 = (n, C.ofintd 0) ∉ SplitC2.I1.RO.m`. The `r5` sample doesn't touch that map; `inv_cpa` says every key in it has its nonce in `BNR.lenc`, but `n = p.\`1 ∉ BNR.lenc`. Discharge the sample then close with the unfolded invariant.
