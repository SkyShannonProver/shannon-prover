# Tree-0.1 · turn 4 · commit_tactic

<!-- session 6b0b5dc3-3078-4ce2-9ba9-d020a8ebd8c4 · 2026-06-09T00:40:09.270Z -->

**Intent:** `commit_tactic`  
**Payload:** `swap{1} 7 -5.`

---

Inlined. Now both programs have the abstract calls `A.choose` and `A.guess` aligned, but the left samples `y` late (position 7) while the right samples it early (position 2). I'll lift the left's `y` sampling up to align the sampling order.
