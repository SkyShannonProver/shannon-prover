# Tree-0.0 · turn 32 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:13:25.556Z -->

**Intent:** `probe_tactic`  
**Payload:** `if{1}; auto.`

---

`if{1}; auto` produced pure goals but `smt(dBlock_uffu)` couldn't close them. Let me probe `if{1}; auto.` alone to read the exact residual logic smt must prove.
