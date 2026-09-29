# Tree-0.0 · turn 5 · probe_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T17:58:24.944Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp; while (={p2, c2, n, a, p0, Mem.lc, Mem.log, glob BNR, UFCMA.log, UFCMA.cbad1, UFCMA_l.lbad1, RO.m, SplitC2.I2.RO.m, SplitD.ROF.RO.m} /\ p{1} = p{2} /\ UFCMA_li.i{2} = nth0 /\ UFCMA_li.cbadi{2} = b2i (nth0 < size UFCMA_l.lbad1{2}) /\ UFCMA_li.badi{2} = (nth0 < size UFCMA_l.lbad1{2} /\ (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`1 = (nth (w1, w2) UFCMA_l.lbad1{2} nth0).`2)); auto.`

---

`sim` can't infer equalities because of the one-sided side-2 invariant facts mixed into the post. I'll prove this identical prefix manually: `wp` to absorb statements 10–11, a relational `while` carrying the equalities plus the (frame-preserved) side-2 facts, then `auto`. Let me probe the combined tactic.
