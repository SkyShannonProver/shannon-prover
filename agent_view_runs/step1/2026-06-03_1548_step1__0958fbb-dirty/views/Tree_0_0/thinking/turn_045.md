# Tree-0.0 · turn 45 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:13:35.221Z -->

**Intent:** `probe_tactic`  
**Payload:** `have -> : Pr[MainD(G2, RO).distinguish() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m : res] by apply (FiniteRO.pr_RO_FinRO_D _ G2 &m tt (fun (b:bool) => b)); move=> ?; exact dblock_ll.`

---

No pre-verified route, so I'll do the `pr_RO_FinRO_D` rewrite myself: `MainD(G2,RO)` → `MainD(G2,FinRO)`, discharging the `is_lossless dblock` hypothesis with `dblock_ll`. Probing a `have ->`.
