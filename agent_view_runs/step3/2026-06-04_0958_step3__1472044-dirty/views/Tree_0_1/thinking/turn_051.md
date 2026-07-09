# Tree-0.1 · turn 51 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:41:17.920Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO), SplitC1.I2.RO), SplitD.ROF.RO).get.`

---

The tag reduces to: `b = RO block at (n,0)`, `(r,s)=mk_rs b`, `t = poly1305 r s (topol a c2) = s + eval r (...)`. With `mk_rs_ofpair`, `(r,s)` are exactly the `ROin`/`ROout` values at `(n,0)`, which are **fresh** (n∉lenc, and inv gives ROin/ROout domains ⊆ lenc), so `s` is uniform → `t` uniform via a `rnd` bijection `s ↦ s + eval`. Let me inline the `RO_DOM.get` to expose the routing.
