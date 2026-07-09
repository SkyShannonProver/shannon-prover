# Tree-0.0 · turn 55 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:21:14.237Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 3 : (={glob A} /\ OpCCRO.OCC.gs{1} = RO.m{2}).`

---

`FinRO.get(x) = oget RO.m.[x]` — pure read-only lookup. So `OpCCRO.OCC.gs{1}=RO.m{2}` is preserved, exactly like the first half. Committing the seq cut (qualified invariant).
