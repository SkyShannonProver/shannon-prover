# Tree-0.1 · turn 16 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:09:03.678Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0 a0 c0 gs0).`

---

Subgoal (A) done. Now subgoal (B): the `Poly.mac` step, with `c{1}` correctly bound to the chacha output. Peel with `poly_spec`.
