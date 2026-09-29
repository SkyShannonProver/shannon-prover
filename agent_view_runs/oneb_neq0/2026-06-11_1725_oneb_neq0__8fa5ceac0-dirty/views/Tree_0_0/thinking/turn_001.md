# Tree-0.0 · turn 1 · commit_tactic

<!-- session 65a03146-4314-4dde-8eb7-c7f8ece3205c · 2026-06-12T00:26:45.913Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply/negP=> /(congr1 (fun b=> b.[0])) /=; rewrite /oneb /zerob !offunE //; exact/Octet.onew_neq0.`

---

I'll start by reading the latest workspace view to see the current proof state.

`Octet.onew_neq0` exists. Now let me check the `Word` theory's `offunE` form.
