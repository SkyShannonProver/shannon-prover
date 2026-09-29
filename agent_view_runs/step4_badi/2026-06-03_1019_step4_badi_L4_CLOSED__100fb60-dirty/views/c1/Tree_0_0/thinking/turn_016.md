# Tree-0.0 · turn 16 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T18:00:47.917Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto; smt().`

---

Side condition needs `cbadi = b2i(nth0 < size lbad1) = 0` from the range fact. Discharge with `auto` then `smt`.
