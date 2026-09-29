# Tree-0.0 · turn 13 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:42:32.422Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hA := SplitD.pr_RO_split (G4(A)) (fun _ (r:bool) => r) &m (); rewrite /= in hA; rewrite hA.`

---

The bridge worked — LHS is now `Split0.IdealAll.MainD(G4(A), Split0.IdealAll.RO)`. Now apply the domain split `SplitD.pr_RO_split`.
