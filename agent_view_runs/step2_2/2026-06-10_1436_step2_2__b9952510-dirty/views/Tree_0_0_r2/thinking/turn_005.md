# Tree-0.0.r2 · turn 5 · probe_tactic

<!-- session 9c6ff196-6193-4d35-b3d1-45aa33af05e6 · 2026-06-10T22:16:58.948Z -->

**Intent:** `probe_tactic`  
**Payload:** `apply (IH c); [ by rewrite -Hlc' | exact Hdec | rewrite take_oversize 1:/# Hns' mem_undup -Hlc'; apply/mapP; exists c => /=; exact Hc ].`

---

Now apply the invariant's universally-quantified hypothesis and discharge the three premises.
