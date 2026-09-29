# Tree-0.1 · turn 25 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:11:55.445Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp; exists* OCC.gs{1}, k{1}, n{1}, c{1}; elim* => gs0 k0 n0 c0; call{1} (chacha_spec k0 n0 c0 gs0).`

---

Then-branch. Absorb the trailing `result <- Some(...)` with `wp`, then peel `ChaCha.enc` via `chacha_spec` (its message arg receives `c`).
