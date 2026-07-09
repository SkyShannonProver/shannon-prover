# Tree-0.0 · turn 103 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:50:47.494Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; while (DoubleQuery.bad /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad)); inline*; auto; sp; if; auto; smt().`

---

Now the Sample-side bad-preservation hoare. `Sample.f` is simpler (no inner `if`). Probing the combined closer.
