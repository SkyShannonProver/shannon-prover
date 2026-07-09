# Tree-0.0 · turn 36 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:58:06.125Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &m0 z; inline FinRO.get; wp; skip.`

---

Now the loop-body phoare goal. Let me introduce, inline `FinRO.get` (which just reads `RO.m`), absorb assignments, and inspect the residual.
