# Tree-0.0 · turn 17 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:50:26.425Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &hr H; split; first by smt(dbool_ll); move=> v hv; rewrite /predT /=; case (j{hr} = i{hr}) => hji; case v => hv2; rewrite ?big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

`split` cleanly gives goal1 `weight {0,1}=1%r` and goal2 the forall. Let me probe a full closer: lossless via `dbool_ll`, then case-split `j=i` and `v`, expand `big_cons`, and close each leaf with XOR algebra.
