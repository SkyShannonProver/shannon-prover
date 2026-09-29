# Tree-0.0 · turn 1 · commit_tactic

<!-- session 2a906b42-b9e2-4eca-b55e-ed59a3848696 · 2026-06-11T15:08:25.348Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondt{1} 5; first by auto => />.`

---

I'm resuming the `equiv_step4` proof at the (t1∉ROout, t2∈ROout, t1∉RO.m, t2∉RO.m) subcase of the iter_perm swap argument. The pattern from the already-closed sibling subcases applies: resolve the four `if` guards with `rcondt` (both keys are fresh in RO.m), couple the samples with `auto`, then close with a `set_setE` commute since the two sides write RO.m in opposite order.

Left `if`s sit at positions 5 and 17; right at 4 and 10. First guard is directly implied by the precondition.
