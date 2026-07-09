# Tree-0.0 · turn 8 · commit_tactic

<!-- session a51e628e-7b92-45c6-b528-b64183d9b981 · 2026-06-10T22:33:55.694Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h2 := pr_RO_FinRO_D (fun (_:nonce*C.counter) => dblock_ll) (G4(A)) &m () (fun (r:bool) => r); rewrite /= in h2; rewrite -h2.`

---

H1 closed. Now H2: convert `FinRO`→`RO` via `pr_RO_FinRO_D`, mirroring step1's idiom (`have := ...; rewrite /= in h; rewrite -h`).
