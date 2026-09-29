# Tree-0.0 · turn 56 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:21:59.211Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OCC(IFinRO)).init GenChaChaPoly(OCC(IFinRO)).kg IFinRO.init.`

---

`FinRO.get` is read-only — invariant safe. Now the prefix. Per the advisor, I'll inline the LHS wrappers down to the bare `FinRO.init()` call (not inlining `FinRO.init` itself). Probing the targeted inline to see the exposed structure.
