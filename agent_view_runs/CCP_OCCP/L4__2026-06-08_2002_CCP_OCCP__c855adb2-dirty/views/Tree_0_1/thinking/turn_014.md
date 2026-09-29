# Tree-0.1 · turn 14 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:08:40.229Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs0 k0 n0 p0; call{1} (chacha_spec k0 n0 p0 gs0).`

---

Subgoal (A): the `ChaCha.enc` step. Peel with `chacha_spec`.
