# Tree-0.0 · turn 21 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:51:40.872Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> _ v hv; rewrite /predT /=; case (j{hr} = i{hr}) => hji; case v => hv2; rewrite ?big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

Now the second `&&` component. Intro (discarding the `weight=1` antecedent), reduce `predT`, case-split, expand `big_cons`, and close with XOR algebra. Let me probe.
