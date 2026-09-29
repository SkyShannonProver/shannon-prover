# Tree-0.0 · turn 33 · probe_tactic

<!-- session 4b39f4e6-16b1-4e04-89ab-2fdac6da9759 · 2026-06-05T11:15:06.988Z -->

**Intent:** `probe_tactic`  
**Payload:** `if{1}; sp; if{1}; auto; smt(dBlock_uffu).`

---

Let me read the exact residual pure goals from the probe preview.

`if{1}; auto` doesn't reduce the one-sided LHS body — `auto` can't step through the `if` guards (it leaves the inner `if`/sample unprocessed, which is why smt then failed). I'll split both `if`s explicitly with `sp` between them, then let `auto` handle the one-sided sample (lossless) and `smt` close the `bad`/lossless logic. Probing the combined closer.
