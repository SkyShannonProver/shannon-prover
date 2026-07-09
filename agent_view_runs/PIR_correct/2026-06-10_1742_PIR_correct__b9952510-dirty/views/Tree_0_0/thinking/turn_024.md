# Tree-0.0 · turn 24 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:52:43.220Z -->

**Intent:** `probe_tactic`  
**Payload:** `case (j{hr} = i{hr}) => hji; case v => hv2; rewrite ?big_cons /=; smt(xorwA xorwC xorw0 xorwK).`

---

`predT` reduced cleanly. Now case-split on `j=i` and `v`, expand `big_cons`, and close with XOR algebra. Let me probe the uniform closer.
