# Tree-0.0 · turn 1 · probe_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T17:55:46.901Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 13 13 : (={Mem.lc, Mem.log, glob BNR, UFCMA.log, UFCMA.cbad1, UFCMA_l.lbad1, RO.m, SplitC2.I2.RO.m, SplitD.ROF.RO.m} /\ ={n, a, c1, p0, t0} /\ p{1} = p{2} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)).`

---

I'll start by loading the proof-intent tool schema, then orient myself on the exact goal structure.

I have a clear picture of the goal. The divergence is entirely inside the `if (cbad1 < qenc /\ size lt <= qdec)` block at top-level statement 13: the right side conditionally resamples `t0` (as `t1`) to instrument `badi` for index `nth0`. The suffix (14–26) is identical, the prefix (1–11) is identical, and statement 12 (`t0 <$ dpoly_out`) must stay uncommitted until I case-split, because which sample couples to the left's depends on the case.

My plan: `seq 13 13 : J` to cut after the divergent `if`, handle the identical suffix once, then within the head do `seq 11 11` + case analysis. Let me first probe the seq cut to validate the index and shape.
