# Tree-0.0 · turn 2 · commit_tactic

<!-- session 65a03146-4314-4dde-8eb7-c7f8ece3205c · 2026-06-12T00:27:03.680Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply/negP=> heq; have := congr1 (fun b=> b.[0]) oneb zerob heq; rewrite /oneb /zerob !offunE //; exact/Octet.onew_neq0.`

---

The lambda inside a view isn't accepted. I'll switch to an explicit `have := congr1 ...` form.
