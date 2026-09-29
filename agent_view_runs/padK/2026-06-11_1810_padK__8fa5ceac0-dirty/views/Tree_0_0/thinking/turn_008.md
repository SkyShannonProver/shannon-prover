# Tree-0.0 · turn 8 · commit_tactic

<!-- session bf054ba6-9878-40db-bcfd-3a67ca2bd8e9 · 2026-06-12T01:13:51.255Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite take_size_cat // drop_size_cat //.`

---

All indices are clean. Now splitting the concatenation: `take (size m)` and `drop (size m)` over `m ++ ...`.
