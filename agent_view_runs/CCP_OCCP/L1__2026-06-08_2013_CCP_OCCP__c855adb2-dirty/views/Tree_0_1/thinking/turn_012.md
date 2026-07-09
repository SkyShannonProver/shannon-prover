# Tree-0.1 · turn 12 · commit_tactic

<!-- session 66372df5-7f4c-455e-92d6-975e7d4c71cc · 2026-06-09T03:19:40.723Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* (glob OCC){1}, k{1}, n{1}, p{1}; elim* => gs kk nn pp; call {1} (chacha_spec kk nn pp gs).`

---

Now generalize side-1 values and apply `chacha_spec` to the LHS call.
