# Tree-0.1 · turn 10 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:06:29.552Z -->

**Intent:** `commit_tactic`  
**Payload:** `exists* OCC.gs{1}, k{1}, n{1}, p{1}; elim* => gs1 k1 n1 p1; call{1} (chacha_spec k1 n1 p1 gs1).`

---

Only `ChaCha.enc` remains. Peel it with `chacha_spec`.
