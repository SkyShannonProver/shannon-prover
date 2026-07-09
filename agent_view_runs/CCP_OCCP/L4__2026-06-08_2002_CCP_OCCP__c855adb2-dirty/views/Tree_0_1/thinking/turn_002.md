# Tree-0.1 · turn 2 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:03:33.501Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc*.`

---

I have the specs I need. The plan: `proc*` to get a statement-level goal, then `call (_: ={glob OCC, glob I})` on the abstract adversary to generate per-oracle equivalence subgoals (init/kg/enc/dec), discharging enc/dec via the `chacha_spec`/`poly_spec` phoare bridges.

Let me commit the first step.
