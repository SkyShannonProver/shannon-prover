# Tree-0.1.1 · turn 19 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:43:50.392Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m0; rnd; wp; rnd; skip => /=; rewrite /inv_cpa; smt(@SmtMap).`

---

Side goal: `x5 = (n, C.ofintd 0) ∉ SplitC2.I2.RO.m`, again from `inv_cpa` (the `ROout` clause) since `n ∉ BNR.lenc` and these statements only touch `ROin`. Discharging the two samples and assignments backward.
