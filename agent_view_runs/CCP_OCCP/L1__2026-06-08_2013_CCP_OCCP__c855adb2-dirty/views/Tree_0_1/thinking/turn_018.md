# Tree-0.1 · turn 18 · commit_tactic

<!-- session 66372df5-7f4c-455e-92d6-975e7d4c71cc · 2026-06-09T03:20:55.664Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; exists* (glob OCC){1}, k{1}, n{1}, a{1}, c{1}; elim* => gs kk nn aa cc0; call {1} (poly_spec kk nn aa cc0 gs); skip; smt().`

---

Proving the Poly.mac prefix with the same `poly_spec` pattern, closing in one shot.
