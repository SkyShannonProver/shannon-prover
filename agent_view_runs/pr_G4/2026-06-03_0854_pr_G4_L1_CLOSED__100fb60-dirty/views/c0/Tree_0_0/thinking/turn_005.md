# Tree-0.0 · turn 5 · commit_tactic

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:03:55.881Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; do 4! rnd predT; call (choose_ll G4.O ll_dec); auto.`

---

The oracle losslessness fact `ll_dec` is in context. Now I'll prove the prefix terminates with probability 1: absorb the assignments and samples, and use `choose_ll` for the adversary call. Let me try a combined closer.
