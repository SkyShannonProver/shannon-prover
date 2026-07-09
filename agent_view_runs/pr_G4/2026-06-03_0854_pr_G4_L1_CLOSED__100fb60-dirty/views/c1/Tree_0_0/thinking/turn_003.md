# Tree-0.0 · turn 3 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:28:46.126Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &hr hs u u' r0 r'0 [h] hrest; rewrite !mapP; smt().`

---

`map_f` alone didn't close it — smt likely needs to reduce the tuple projection / pick the witness. Let me try with `mapP`.
