# Tree-0.0 · turn 13 · probe_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:49:38.733Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(pr_RO_FinRO_D _ (G4(A)) &m tt (fun (r:bool) => r)).`

---

Parses now but "nothing to rewrite" — the predicate `p` needs to be concrete (idfun). Let me supply `x:=tt` and `p:=fun r=>r` explicitly, with the losslessness hypothesis as a hole.
