# Tree-0.0 · turn 18 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:51:06.038Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr H; split; first by smt(dbool_ll); move=> _ v hv; rewrite /predT /=; case (j{hr} = i{hr}) => hji; case v => hv2; rewrite ?big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

The `&&` is asymmetric — `split`'s second goal carries a `weight=1 =>` antecedent. I need to discard it before introducing `v`. Let me adjust with `move=> _ v hv`.
