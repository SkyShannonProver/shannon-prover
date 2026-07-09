# Tree-0.0 · turn 5 · commit_tactic

<!-- session 1959f737-444b-4631-b310-fb150d0581af · 2026-06-11T23:57:25.380Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; while (c0{1} = c{2} /\ i{1} = i{2} + 1 /\ p0{1} = p{2}); auto=> /#.`

---

First iteration peeled — left positions 5–7 now mirror the right's initial sample. Now `wp` plus the synchronized while with invariant `i{1} = i{2}+1`.
