# Tree-0.0 · turn 14 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:48:12.090Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr H; split; first by smt(dbool_ll); move=> v hv; rewrite /predT /= !big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

Now I'll discharge the residual: split off the lossless side, reduce `predT`, expand `big_cons`, and let `smt` finish the XOR algebra. Let me probe.
