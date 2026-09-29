# Tree-0.1.0 · turn 18 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:34:41.972Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ n{1} = p{1}.`1 /\ ! (p{1}.`1 \in BNR.lenc{1}) /\ inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall (n0 : nonce) (c3 : C.counter), (n0, c3) \in SplitD.ROF.RO.m{1} => n0 \in p{1}.`1 :: BNR.lenc{1}) /\ p{1} = p{2}).`

---

Rewound to before the seq cut — the full pre is restored, including `p{1} = p{2}`. Now re-issue the seq cut with `p{1} = p{2}` added to the intermediate assertion so the tail can prove the `lenc` equality.
