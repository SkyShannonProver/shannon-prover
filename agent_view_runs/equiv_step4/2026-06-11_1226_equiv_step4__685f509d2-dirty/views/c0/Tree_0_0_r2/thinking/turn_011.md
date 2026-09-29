# Tree-0.0.r2 · turn 11 · commit_tactic

<!-- session 351c551b-47e9-4b44-8771-01f4aa096d11 · 2026-06-11T16:14:21.408Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &1 &2 />; exists UF.forged{2} UFCMA.bad2{2} UFCMA.cbad2{2} UFCMA.log{2} RO.m{2} Mem.lc{2} ROout.m{2} ns1{2} ns2{2}; smt(filter_uniq undup_uniq mem_filter).`

---

Transitivity accepted; the existence goal shows the witness order. Providing witnesses and discharging the filter/undup facts with smt.
