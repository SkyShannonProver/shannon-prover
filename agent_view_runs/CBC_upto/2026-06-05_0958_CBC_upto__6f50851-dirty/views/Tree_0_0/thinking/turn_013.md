# Tree-0.0 · turn 13 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:16:39.542Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

The while body is focused (a residual entry/exit goal is also queued). Now I need to know the exact inlined form of `PRFi.f` (the lazy RF). Let me find the `RF` theory.

The lazy RF is `if (x \notin m){ r<$dBlock; m.[x]<-r; } return oget m.[x]`. Now inline both `f` calls in the body.
