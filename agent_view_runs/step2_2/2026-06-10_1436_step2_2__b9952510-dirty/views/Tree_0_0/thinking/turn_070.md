# Tree-0.0 · turn 70 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:14:26.573Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> forged_R i_R; split; first by move=> [hb _] hsz; smt().`

---

Now the `forall forged_R i_R` with termination and exit parts. Let me probe intro + the termination conjunct (arithmetic from the invariant's bound).
