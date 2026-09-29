# Tree-0.0 · turn 6 · commit_tactic

<!-- session 89741c4d-97d4-4e85-92cf-0be265f01f88 · 2026-06-09T21:49:36.469Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondf{2} 1; 1: (by auto => /#); by auto => />; smt(size_cat size_map nth_cat).`

---

In the true branch, the precondition's negation forces the inner guard false. Killing the dead branch and closing with the cat/map list facts.
