# Tree-0.0 · turn 9 · commit_tactic

<!-- session 0ecb35e0-bd33-4830-b6e0-0f2d764377d8 · 2026-06-10T21:06:27.974Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> gs k1 k2 [n a cph t]; rewrite /dec /genpoly1305 /get /=; smt().`

---

Now prove the `k`-independence by unfolding `dec`/`genpoly1305`/`get` (which drops `k`).
