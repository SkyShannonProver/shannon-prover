# Tree-0.1 · turn 11 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:05:16.491Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /inv_cpa; smt().`

---

Guard-equivalence goal. The invariant gives `lenc{1}=lenc{2}` and `p{1}=p{2}`, so the guards coincide by congruence — I just need to unfold `inv_cpa`.
