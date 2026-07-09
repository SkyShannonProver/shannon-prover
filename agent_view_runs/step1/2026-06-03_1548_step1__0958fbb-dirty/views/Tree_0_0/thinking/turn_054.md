# Tree-0.0 · turn 54 · lookup_symbol

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:20:56.172Z -->

**Intent:** `lookup_symbol`  
**Payload:** `FinRO`

---

This mirrors the first half: cut `seq 1 3` after the inits with invariant `OCC.gs{1}=RO.m{2}`, then `call`/`chacha_enc2`/`poly_mac2`. But the init prefix now involves coupling two eager `FinRO.init` calls plus an extra one-sided `Mem.k` sampling, and I need to confirm the oracle invariant is preserved. Let me get the advisor's read before committing to this branch.

Advisor confirms the plan; the pivot is whether `FinRO.get` is read-only on `RO.m`. Let me look it up.
