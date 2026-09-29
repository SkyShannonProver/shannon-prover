# Tree-0.0 · turn 31 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:07:58.549Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp.`

---

dec is analogous but has the `if (t=t')` branch with `Poly.mac` computed before it; inlining renames LHS locals, so I need to see the real post-`sp` variable names before writing the `seq` cut. Let me probe `proc; inline{1}; sp` and read the resulting goal.
