# Tree-0.0 · turn 94 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:48:38.948Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp; if; auto; smt().`

---

`auto` doesn't wp through the `if`s here. Using the explicit `sp; if; auto; smt()` (worked for the analogous hoare earlier).
