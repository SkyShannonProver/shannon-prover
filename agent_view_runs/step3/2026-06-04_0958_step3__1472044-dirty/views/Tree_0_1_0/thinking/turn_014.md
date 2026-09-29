# Tree-0.1.0 · turn 14 · commit_tactic

<!-- session 2f6ace9e-0667-4196-9f0c-4c90d2bd8e23 · 2026-06-04T17:29:58.681Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Both freshness `if`s resolved, so `r10 = r5` and `r20 = r6` (fresh). The extra-block path (`r4`, `r2`, `if 22`) doesn't affect the tag, since `mk_rs (SplitC1.ofpair (SplitC2.ofpair (r,s), e)) = (r,s)` (lemma `mk_rs_ofpair`). Let me absorb the deterministic tail with `wp` and inspect how `t` is represented.
