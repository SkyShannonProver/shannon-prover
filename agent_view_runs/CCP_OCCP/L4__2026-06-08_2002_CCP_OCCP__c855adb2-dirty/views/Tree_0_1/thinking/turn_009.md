# Tree-0.1 · turn 9 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:06:15.097Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* OCC.gs{1}, k{1}, n{1}, a{1}, c{1}; elim* => gs0 k0 n0 a0 c0; call{1} (poly_spec k0 n0 a0 c0 gs0).`

---

Now RHS is fully absorbed into the precondition (c{2}, t{2} are closed forms). LHS has two pending calls. I'll peel the last one (`Poly.mac`) using the `poly_spec` phoare bridge.
