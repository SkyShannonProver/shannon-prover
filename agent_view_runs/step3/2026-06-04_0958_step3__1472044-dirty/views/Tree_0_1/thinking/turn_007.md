# Tree-0.1 · turn 7 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:03:46.492Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2}).`

---

Now the two adversary runs are the trailing statements with post `b3{1}=b1{2}`. I'll relate them with `call` under the `inv_cpa` invariant (the invariant this file defines exactly for this hop: equal logs/lists/counters across sides, plus the RO-domain ⊆ lenc freshness conditions on the left).
