# Tree-0.0 · turn 52 · commit_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:21:43.527Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

`f_eq` is proven and now in context. Back to the enc-equiv. Plan (per advisor): `proc`, couple the initial sample + set up loop, then `while <bad-conditional inv>` with body `wp; call f_eq; auto`. Committing `proc`.
