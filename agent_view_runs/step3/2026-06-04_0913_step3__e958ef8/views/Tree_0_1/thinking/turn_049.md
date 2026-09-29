# Tree-0.1 · turn 49 · commit_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:48:33.713Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 1 : (c2{1} = c1{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ p0{1} = p0{2} /\ p{1}.`1 = n{1} /\ p{2}.`1 = n{2} /\ Mem.log{1} = Mem.log{2} /\ Mem.lc{1} = Mem.lc{2} /\ BNR.lenc{1} = BNR.lenc{2} /\ BNR.ndec{1} = BNR.ndec{2} /\ !(n{1} \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitC2.I1.RO.m{1} => nn \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitC2.I2.RO.m{1} => nn \in BNR.lenc{1}) /\ (forall nn ci, (nn, ci) \in SplitD.ROF.RO.m{1} => nn \in n{1} :: BNR.lenc{1})).`

---

Back before the `seq`. Now I redo it with `p.\`1 = n` added to the carried relation.
