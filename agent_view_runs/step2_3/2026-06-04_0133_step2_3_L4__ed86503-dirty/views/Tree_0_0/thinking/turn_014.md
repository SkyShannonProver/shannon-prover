# Tree-0.0 · turn 14 · commit_tactic

<!-- session 7c3d23d4-df62-481f-a000-69153e41b769 · 2026-06-04T08:49:57.054Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -(pr_RO_FinRO_D _ (G4(A)) &m tt (fun (r:bool) => r)).`

---

Accepted. Let me check what subgoals this produces (LHS rewritten + losslessness side-goal).

The rewrite produces the losslessness side-goal first, then the rewritten main goal (`MainD(G4,RO)`). Committing it, then I'll discharge the side-goal.
