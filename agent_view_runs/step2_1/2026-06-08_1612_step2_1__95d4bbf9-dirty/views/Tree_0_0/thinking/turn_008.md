# Tree-0.0 · turn 8 · commit_tactic

<!-- session 97e6a0e6-3ebd-4e69-827b-9ef0ceb80f2b · 2026-06-08T23:18:39.768Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &2; case: (c{2}) => n a c0 t /=; rewrite /dec /get /=; smt().`

---

Now destruct, unfold `dec`/`get`, and discharge both branches.
