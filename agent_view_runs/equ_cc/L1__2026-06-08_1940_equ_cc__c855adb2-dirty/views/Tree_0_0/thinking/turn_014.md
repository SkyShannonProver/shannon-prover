# Tree-0.0 · turn 14 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:57:48.958Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hc : size c{hr} = block_size * (i{hr} - 1) by smt().`

---

The chain stopped at `hc` (only `hp1` landed). The goal still has the `forall r0_0` binder from the sample. Let me retry the `size c = block_size*(i-1)` extraction on its own to diagnose.
