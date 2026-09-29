# Tree-0.0 · turn 57 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:23:12.176Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline{1} RealOrcls(GenChaChaPoly(OCC(IFinRO))).init GenChaChaPoly(OCC(IFinRO)).init GenChaChaPoly(OCC(IFinRO)).kg IFinRO.init. inline{2} D(A, G2(FinRO).CCRO).O.init. seq 1 1 : (={glob A, RO.m}). sim. wp. rnd{1}. auto.`

---

LHS now: `FinRO.init(); OCC.gs <- RO.m; k <$ dkey; Mem.k <- k`. RHS: `FinRO.init(); ()<-x; D.O.init()`. Plan: cut after the shared `FinRO.init` with `sim`, then absorb the LHS-only deterministic/lossless tail. Probing the combined prefix closer.
