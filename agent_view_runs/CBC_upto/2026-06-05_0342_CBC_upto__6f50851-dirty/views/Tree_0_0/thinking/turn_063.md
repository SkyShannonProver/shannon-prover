# Tree-0.0 · turn 63 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:38:17.586Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> B; conseq f_eq (_: true ==> true) (_: DoubleQuery.bad = B ==> B => DoubleQuery.bad).`

---

Now prove `f_eqM` from `f_eq` plus a side-2 `bad`-monotonicity hoare via `conseq`. Probing the setup.
