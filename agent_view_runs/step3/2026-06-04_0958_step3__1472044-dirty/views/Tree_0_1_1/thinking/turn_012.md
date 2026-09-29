# Tree-0.1.1 · turn 12 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:37:41.076Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

True branch selected. Now I'll work through the inlined RO sampling. The key facts: `x4 = x5 = x3 = (n, C.ofintd 0)`, and by `inv_cpa` plus `n = p.\`1 ∉ BNR.lenc`, the entry `(n,0)` is fresh in `SplitC2.I1.RO.m` and `SplitC2.I2.RO.m`, so the `notin` guards on those hold. The final `t = poly1305 r5 r6 (topol a0 c3) = r6 + poly1305_eval r5 p` (via `mk_rs_ofpair`), so the coupling pairs left's `r6` sample with right's `t` sample.

Let me absorb the leading assignments.
