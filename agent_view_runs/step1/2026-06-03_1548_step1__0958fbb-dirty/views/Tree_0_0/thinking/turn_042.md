# Tree-0.0 · turn 42 · commit_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:12:14.240Z -->

**Intent:** `commit_tactic`  
**Payload:** `have -> : Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res] = Pr[MainD(G2, RO).distinguish() @ &m : res] by byequiv => //; proc; inline *; sim.`

---

The manager gives a daemon-verified route normalizing the RHS to `MainD(G2, RO).distinguish()` (exposing the `pr_RO_FinRO_D` eager↔lazy rewrite). Committing it.
