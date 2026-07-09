# Tree-0.0 · turn 46 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:14:04.491Z -->

**Intent:** `commit_tactic`  
**Payload:** `have -> : Pr[MainD(G2, RO).distinguish() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m : res] by apply (FiniteRO.pr_RO_FinRO_D _ G2 &m tt (fun (b:bool) => b)); move=> ?; exact dblock_ll.`

---

The `pr_RO_FinRO_D` rewrite is accepted. Let me confirm the RHS now reads `MainD(G2, FinRO)`.

RHS is now `MainD(G2, FinRO).distinguish()` — both sides use `FinRO`, so this mirrors the first half (normalize via `OpCCRO.pr_CCP_OCCP`, invariant `OCC.gs{1}=RO.m{2}`, lemmas `chacha_enc2`/`poly_mac2`). Committing the rewrite.
