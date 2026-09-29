# Tree-0.0.0 · turn 14 · commit_tactic

<!-- session 2f0c9585-75ee-40a7-b7bd-a964dff75341 · 2026-06-06T11:25:28.176Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> c0 i0 p1; split=> [hi hle|]; first by smt(size_eq0 size_ge0).`

---

`=> />` already discharged the entry-invariant. Two obligations remain (termination + exit). Let me split them.
