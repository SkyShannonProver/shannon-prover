# Tree-0.0 · turn 22 · lookup_symbol

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:02:55.761Z -->

**Intent:** `lookup_symbol`  
**Payload:** `RealOrcls`

---

The structural analysis confirms the plan: `seq 1 2 (<inv>)` to cut after the inits (matching A.main calls at left-2/right-3), then `call (_: <inv>); sim`. The invariant is the secret-key relation. I need to confirm where `RealOrcls` stores the key (`Mem.k`?). Let me look it up.
