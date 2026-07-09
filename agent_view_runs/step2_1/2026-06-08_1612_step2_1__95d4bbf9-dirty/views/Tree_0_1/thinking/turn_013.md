# Tree-0.1 · turn 13 · commit_tactic

<!-- session b1d56379-c118-4462-8adc-ddc4d1f41224 · 2026-06-08T23:18:40.476Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &2; rewrite /dec /get /=; smt().`

---

Now unfold `dec` and `get`, then discharge with smt.
