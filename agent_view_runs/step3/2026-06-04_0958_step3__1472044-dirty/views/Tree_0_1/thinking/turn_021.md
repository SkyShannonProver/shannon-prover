# Tree-0.1 · turn 21 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:09:53.836Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).`

---

Back to the pre-`call` state. Now re-issue the adversary `call` with the strengthened invariant — `inv_cpa` plus the `ROF.m ⊆ lenc` freshness conjunct that `equ_cc` needs.
