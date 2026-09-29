# Tree-0.0 · turn 76 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:41:57.595Z -->

**Intent:** `probe_tactic`  
**Payload:** `conseq (_: true ==> true: =1%r) (_: DoubleQuery.bad <=> DoubleQuery.bad{2} ==> DoubleQuery.bad <=> DoubleQuery.bad{2}).`

---

Now `phoare[enc : (bad<=>bad{2}) ==> same] = 1%r`. Splitting into losslessness + bad-preservation via conseq (template pattern). Probing.
