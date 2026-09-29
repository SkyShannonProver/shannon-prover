# Tree-0.0 · turn 4 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:24:58.055Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hL: Pr[D4.sample() @ &1 : res = a] = Pr[D4_6.SampleE.sample(tt) @ &1 : res = a] by byequiv D4_Sample.`

---

Now transform the LHS. Convert `Pr[D4.sample]` to `Pr[SampleE.sample]` via `D4_Sample`.
