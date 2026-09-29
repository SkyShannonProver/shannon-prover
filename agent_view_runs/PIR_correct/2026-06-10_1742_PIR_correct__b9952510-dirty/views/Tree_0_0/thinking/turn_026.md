# Tree-0.0 · turn 26 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:53:27.459Z -->

**Intent:** `probe_tactic`  
**Payload:** `case v => hv2; rewrite /predT in H; rewrite ?big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

The mismatch is `big predT` in `H` vs `big (fun _=>true)` in the goal (my earlier `/predT` unfold broke smt's matching). Let me unfold `predT` in `H` too, then close. Probing the `j=i` branch.
