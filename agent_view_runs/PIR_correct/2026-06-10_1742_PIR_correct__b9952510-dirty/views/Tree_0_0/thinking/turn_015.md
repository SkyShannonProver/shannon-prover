# Tree-0.0 · turn 15 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:49:10.981Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr H; rewrite !big_cons /predT /=; smt(xorwA xorwC xorw0 xorwK dbool_ll).`

---

The `split` behaved oddly on the `&&` (asymmetric boolean and). Let me instead keep the structure intact, rewrite `big_cons` under the binder, and let `smt` handle everything including the lossless side.
