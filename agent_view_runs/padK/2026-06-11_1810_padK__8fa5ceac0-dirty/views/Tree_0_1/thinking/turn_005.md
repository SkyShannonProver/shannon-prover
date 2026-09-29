# Tree-0.1 · turn 5 · commit_tactic

<!-- session 8512144a-73df-4141-a9a7-f90e778517d5 · 2026-06-12T01:13:25.288Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (take_size_cat (size m)) // (drop_size_cat (size m)) // (take_size_cat 32) 1:size_t2os // t2osK.`

---

The condition and branch are nearly concrete. Now simplifying the take/drop over concatenations (with explicit instantiations to hit the right occurrences).
