# Tree-0.0 · turn 12 · commit_tactic

<!-- session 522e5fad-92b1-442a-b331-b9f5b78770f4 · 2026-06-03T17:59:55.326Z -->

**Intent:** `commit_tactic`  
**Payload:** `case (size UFCMA_l.lbad1{2} <= UFCMA_li.i{2} < size UFCMA_l.lbad1{2} + size lt{2}).`

---

Both outer `if`s unfolded. Now the right has the inner range-`if`. I'll case-split on that range guard (`i{2} = nth0`).
