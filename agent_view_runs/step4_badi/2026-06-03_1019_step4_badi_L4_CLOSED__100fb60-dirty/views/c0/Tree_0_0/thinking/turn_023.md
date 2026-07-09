# Tree-0.0 · turn 23 · probe_tactic

<!-- session 7d6b85e1-efc5-4558-ab30-99a9e554877b · 2026-06-03T17:36:04.898Z -->

**Intent:** `probe_tactic`  
**Payload:** `call (_: (glob A){1} = (glob A){2} /\ Mem.lc{1} = Mem.lc{2} /\ Mem.log{1} = Mem.log{2} /\ BNR.lenc{1} = BNR.lenc{2} /\ BNR.ndec{1} = BNR.ndec{2} /\ UFCMA.log{1} = UFCMA.log{2} /\ UFCMA.cbad1{1} = UFCMA.cbad1{2} /\ UFCMA_l.lbad1{1} = UFCMA_l.lbad1{2} /\ RO.m{1} = RO.m{2} /\ SplitC2.I2.RO.m{1} = SplitC2.I2.RO.m{2} /\ SplitD.ROF.RO.m{1} = SplitD.ROF.RO.m{2} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)).`

---

Now I'll cross the adversary call. Let me probe `call (_: INV)` directly with my full relational invariant (flat conjunction) to see whether EC leaves the post-implication as a residual or requires a `conseq` first.
