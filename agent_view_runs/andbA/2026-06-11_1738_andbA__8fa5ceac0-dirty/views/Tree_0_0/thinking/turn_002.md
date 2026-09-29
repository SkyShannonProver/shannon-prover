# Tree-0.0 · turn 2 · commit_tactic

<!-- session 62c3d798-e154-431f-bc50-d378207520fe · 2026-06-12T00:39:39.492Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> b1 b2 b3; apply/blockP=> i ge0_gti_n; rewrite !andbE // andwA.`

---

The pattern is clear from xorbA. I'll commit the analogous proof using word-level associativity `andwA`.
