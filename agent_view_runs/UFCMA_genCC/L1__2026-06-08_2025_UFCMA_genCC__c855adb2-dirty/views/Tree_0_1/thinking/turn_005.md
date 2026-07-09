# Tree-0.1 · turn 5 · commit_tactic

<!-- session 71eefeb0-ba0c-4a92-8c5d-eb48f1c8df06 · 2026-06-09T04:00:18.188Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

`FinRO.get` is the eager full-map read (`result <- oget RO.m.[x]`, no sampling, `RO.m` unchanged). The right side is now fully deterministic straight-line code with an empty left side. Let me absorb it all with `sp`.
