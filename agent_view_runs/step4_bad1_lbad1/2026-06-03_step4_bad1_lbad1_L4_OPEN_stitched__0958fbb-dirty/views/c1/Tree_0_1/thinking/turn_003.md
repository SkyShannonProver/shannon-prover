# Tree-0.1 · turn 3 · probe_tactic

<!-- session 85867cf0-a726-4a8a-bf95-4c01d247dbb7 · 2026-06-03T20:05:51.221Z -->

**Intent:** `probe_tactic`  
**Payload:** `skip.`

---

This is a pRHL goal with both programs fully consumed (the post is already the WP, containing the `RO.m.[x1 <- r]` updates). The parent failed with `move=> />; rewrite /check_plaintext /=; progress; smt(...)`. To diverge, I want to reduce the empty-program equiv to an ambient implication first via `skip`, then discharge. Let me probe `skip.` to confirm the programs are empty.
