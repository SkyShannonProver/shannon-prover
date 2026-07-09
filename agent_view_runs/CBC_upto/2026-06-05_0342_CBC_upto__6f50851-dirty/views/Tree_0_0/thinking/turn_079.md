# Tree-0.0 · turn 79 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:43:03.377Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; while (DoubleQuery.bad <=> DoubleQuery.bad{2}); inline*; auto; smt().`

---

Now the bad-preservation hoare `[enc : (bad<=>bad{2}) ==> same]` (bad{2} frozen true; enc preserves bad monotonically). This is a one-sided hoare, so `auto` can wp through the `if`s. Probing `proc; while (inv); inline*; auto; smt()`.
