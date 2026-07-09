# Tree-0.1 · turn 27 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:12:57.026Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ n{1} = p{1}.`1 /\ ! (p{1}.`1 \in BNR.lenc{1}) /\ inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall (n0 : nonce) (c3 : C.counter), (n0, c3) \in SplitD.ROF.RO.m{1} => n0 \in p{1}.`1 :: BNR.lenc{1})).`

---

Now I'll split off the `ChaCha.enc ~ cc` step (which `equ_cc` proves) from the tag step with `seq 1 1`, carrying an intermediate that records the ciphertext equality, the nonce/ad equalities, the freshness facts, and the invariant pieces the tag step needs.
