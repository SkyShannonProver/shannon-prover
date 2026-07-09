# Tree-0.0 · turn 28 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:53:57.761Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite big_cons /=; rewrite /predT in H; smt(xorwA xorwC xorw0 xorwK).`

---

Now a single leaf `[j=i, v=true]`. Let me probe its closer: expand `big_cons`, unify `predT` in `H`, then XOR algebra.
