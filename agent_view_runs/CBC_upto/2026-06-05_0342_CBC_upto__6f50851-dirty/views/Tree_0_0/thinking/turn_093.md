# Tree-0.0 · turn 93 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:48:17.674Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto; smt(size_ge0).`

---

Int-hoare B: body doesn't touch `i,p`, so `auto` should wp through to `pre ⟹ post`. Probing `auto; smt(size_ge0)`.
