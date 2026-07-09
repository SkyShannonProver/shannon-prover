# Tree-0.0 · turn 2 · commit_tactic

<!-- session a51e628e-7b92-45c6-b528-b64183d9b981 · 2026-06-10T22:23:49.756Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -(SplitC2.pr_RO_split (G8(A)) (fun _ (r:bool) => r) &m ()).`

---

`congr` gave 2 goals; goal 1 is the CPA/G8 term. Now collapse the paired RO via `SplitC2.pr_RO_split` (backwards).
