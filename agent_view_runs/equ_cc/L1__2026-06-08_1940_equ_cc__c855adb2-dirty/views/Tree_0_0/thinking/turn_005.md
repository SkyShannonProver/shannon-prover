# Tree-0.0 · turn 5 · commit_tactic

<!-- session eaf07ef5-71a1-4d41-95c4-abae017c95e5 · 2026-06-09T02:49:14.058Z -->

**Intent:** `commit_tactic`  
**Payload:** `rcondf{1} 5.`

---

Inlining exposed the structure. The `else` branch (counter ≠ 0) is the live path through the plain `ROF` RO; the `if (SplitD.test x)` then-branch is dead. Let me check the `C` counter theory for the exact `toint`/`ofintd` round-trip lemma name before eliminating that branch.

The round-trip lemma is `C.ofintdK : 0 <= x < max_counter+1 => C.toint (C.ofintd x) = x`. Now I'll eliminate the dead `test`-true branch with `rcondf{1} 5`.
