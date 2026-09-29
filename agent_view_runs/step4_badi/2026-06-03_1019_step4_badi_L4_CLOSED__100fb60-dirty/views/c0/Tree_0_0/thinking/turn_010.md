# Tree-0.0 · turn 10 · probe_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:29:06.152Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 10 13 : (={glob A, glob Mem, glob BNR, UFCMA.log, UFCMA.cbad1, UFCMA_l.lbad1, RO.m, SplitC2.I2.RO.m, SplitD.ROF.RO.m} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)).`

---

Now I'll set up the cut: absorb the 10/13 init statements and establish a relational invariant before the adversary call. Let me probe the `seq` with my invariant.
