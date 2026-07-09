# Tree-0.1.0 · turn 1 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:21:38.041Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (n{1}), (SplitC2.I1.RO.m{1}), (SplitC2.I2.RO.m{1}).`

---

I'll start by loading the proof intent tool, then drive a divergent opener. The parent's `call (equ_cc ...)` failed with `call_needs_instantiation` — the lemma's memory-map and value parameters (`mr0 = ROin.m{1}`, `ms0 = ROout.m{1}`, `n0`) must be abstracted out of the current state with `exists*` before `call` can unify them. That's a structurally different opener than a bare `call`.
