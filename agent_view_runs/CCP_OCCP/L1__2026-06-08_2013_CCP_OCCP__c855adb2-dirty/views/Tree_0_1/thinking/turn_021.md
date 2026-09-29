# Tree-0.1 · turn 21 · commit_tactic

<!-- session 66372df5-7f4c-455e-92d6-975e7d4c71cc · 2026-06-09T03:21:26.361Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; exists* (glob OCC){1}, k{1}, n{1}, c{1}; elim* => gs kk nn cc0; call {1} (chacha_spec kk nn cc0 gs); skip; smt().`

---

Then-branch: same `chacha_spec` bridge (message arg is `c` here). Closing in one shot.
