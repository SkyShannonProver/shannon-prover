# Tree-0.0 · turn 7 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:27:48.347Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[D6.sample() @ &2 : finv res = a] = Pr[D4_6.SampleWi.sample(tt, 5) @ &2 : finv res = a] by byequiv D6_Sample=> //.`

---

LHS done (explicit memory-arg syntax was the issue; unification works). Now I need `Pr[D6...]`. Let me check the unit literal and how `SampleWi`/`SampleE` calls are written in practice.

`tt` is correct, so the earlier `by byequiv` failed on a residual subgoal. Let me convert `Pr[D6]` to `Pr[SampleWi(tt,5)]` via `D6_Sample`, closing the correspondence with `=> //`.
