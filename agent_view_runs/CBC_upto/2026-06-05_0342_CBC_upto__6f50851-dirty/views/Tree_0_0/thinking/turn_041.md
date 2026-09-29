# Tree-0.0 · turn 41 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:17:59.878Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline*; auto; sp; if{1}; auto; smt(dBlock_uffu).`

---

After `inline*; auto`, the LHS residual head is `bad<-true` (deterministic), so I need `sp` first, then `if{1}` for the inner `if`. Probing the corrected closer.
