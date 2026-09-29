# Tree-0.0 · turn 11 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:48:08.074Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(pr_RO_FinRO_D (fun (_:nonce*C.counter) => dblock_ll) (G4(A)) &m () (fun (r:bool) => r)).`

---

`pr_RO_FinRO_D` takes a losslessness hypothesis first, then `D0 &m x p`. Let me probe the FinRO→RO rewrite on the LHS.
