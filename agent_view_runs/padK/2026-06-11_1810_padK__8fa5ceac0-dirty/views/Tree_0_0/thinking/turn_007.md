# Tree-0.0 · turn 7 · commit_tactic

<!-- session bf054ba6-9878-40db-bcfd-3a67ca2bd8e9 · 2026-06-12T01:13:42.585Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: 48 + (size m - size m %% 16) - (16 - size m %% 16) = size m + 32 by ring.`

---

Now the same for the drop index, which equals `size m + 32`.
