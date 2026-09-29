# Tree-0.1.0 · turn 5 · probe_tactic

<!-- session 6ba4c334-113f-4b01-a999-5d6b459f95b9 · 2026-06-03T20:31:04.332Z -->

**Intent:** `probe_tactic`  
**Payload:** `if.`

---

I now understand the state: tactic #19 (the parent's smt) actually *succeeded* and closed a subgoal (6→5). I'm now on a **different** pending subgoal — a pRHL judgment with a residual `RO.sample` conditional (`if (x ∉ RO.m) RO.m.[x] <- r`) on both sides, which is why `skip`/`auto`/`move=>` all fail. The post is already in the 4-way wp/branch form. The guards `x1{1}∉RO.m{1}` / `x1{2}∉RO.m{2}` are equal under the precondition (`RO.m{1}=RO.m{2}`, `x1{1}=x1{2}`). Let me probe a two-sided `if`.
