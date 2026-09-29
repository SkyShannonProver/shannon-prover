# Tree-0.0 · turn 10 · probe_tactic

<!-- session 15e4fb16-d3bb-49b9-98b4-c4b814936863 · 2026-06-06T22:37:11.484Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> sz; inline OCC(I).cc; wp; skip.`

---

Inline worked, but it introduced program-local vars `k0,n0,c0` shadowing the logical ones (line 4: `cc OCC.gs k0{!hr} n0{!hr} c0`). These collapse away under `wp`/`sp`. Let me probe the full forward-substitution to see the resulting pure logical goal.
