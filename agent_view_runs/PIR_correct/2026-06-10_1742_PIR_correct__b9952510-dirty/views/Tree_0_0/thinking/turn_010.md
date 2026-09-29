# Tree-0.0 · turn 10 · probe_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:46:22.532Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto.`

---

`big_cons`: `big P F (x::s) = if P x then F x +^ big P F s else big P F s`. Let me probe `auto` on the body to see the residual XOR-sum obligation.
