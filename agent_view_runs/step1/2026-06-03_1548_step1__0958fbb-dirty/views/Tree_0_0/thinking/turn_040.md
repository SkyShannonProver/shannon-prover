# Tree-0.0 · turn 40 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:11:57.504Z -->

**Intent:** `commit_tactic`  
**Payload:** `congr.`

---

congr strips the negation cleanly. The second half is subtler — it uses the **OpCCRO** clone (FinRO eager-sampled) on the left vs lazy `IndRO`/`RO` on the right, so it needs an eager↔lazy hop (`pr_RO_FinRO_D`) plus `chacha_enc2`/`poly_mac2`. Let me commit congr and consult the manager's verified routes.
