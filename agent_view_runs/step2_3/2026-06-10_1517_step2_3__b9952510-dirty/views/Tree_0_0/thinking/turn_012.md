# Tree-0.0 · turn 12 · commit_tactic

<!-- session e2cbd3bf-b9d4-4009-a5ab-a91bfa3420b5 · 2026-06-10T22:42:21.124Z -->

**Intent:** `commit_tactic`  
**Payload:** `have ->: Pr[MainD(G4(A), RO).distinguish() @ &m : res] = Pr[Split0.IdealAll.MainD(G4(A), Split0.IdealAll.RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

"nothing to rewrite" — the goal's `MainD`/`RO` may belong to a different clone than `SplitD`'s. Let me check what `MainD`/`RO`/`FinRO` and `pr_RO_FinRO_D` resolve to.

The bare `MainD`/`RO`/`FinRO` come from the top-level `clone import FullRO` at line 602 — a *different* clone than `Split0.IdealAll`. Let me read line 602's clone params to confirm it matches Split0.

Confirmed identical clone params. The goal's `RO` is the top-level FullRO, distinct from `Split0.IdealAll.RO`. I need to first byequiv-bridge to the Split0 clone before applying the domain split. Committing that bridge.
