# Tree-0.0 · turn 19 · probe_tactic

<!-- session 85d57332-b3ec-4f7b-92f2-424aa26a1fe9 · 2026-06-04T16:23:46.426Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &1 &2; rewrite /inv_cpa; smt().`

---

Active goal is the guard equivalence — provable since `inv_cpa` gives `BNR.lenc{1}=BNR.lenc{2}` and `p{1}=p{2}`. Let me probe unfolding `inv_cpa` and discharging with smt.
