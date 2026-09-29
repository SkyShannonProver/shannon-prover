# Tree-0.0 · turn 14 · commit_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:21:18.116Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in SplitC1.I2.RO.m{1} => n \in BNR.lenc{1}) /\ (forall n c, (n,c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1})).`

---

The invariant typechecks and queues 3 oracle subgoals. Let me commit the `call`.
