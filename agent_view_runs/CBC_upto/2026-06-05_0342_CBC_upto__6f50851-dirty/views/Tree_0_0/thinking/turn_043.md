# Tree-0.0 · turn 43 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:18:40.944Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline*; sp; rcondt{1} 1.`

---

ELSE branch (good/fresh sampling, `x∉qs`): both sample fresh, couple `r`. Since `fdom PRFi.m{1}=qs{1}` and `x∉qs`, the LHS inner `if(x∉m)` is true. Let me inline, align with `sp`, and force the LHS branch with `rcondt{1}`.
