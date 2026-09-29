# Tree-0.1.1 · turn 8 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:35:32.596Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1}.`

---

First subgoal done. Now the tag step: the left runs `Poly(...).mac`, which fetches the block at counter 0 from the split RO (sampling fresh `r <$ dpoly_in`, `s <$ dpoly_out`, `e <$ dextra_block` since `(n,0)` is fresh), yielding `t = poly1305 r s (topol a c2) = s + poly1305_eval r (topol a c2)`; the right samples `t <$ dpoly_out` directly. The coupling is `t = s + poly1305_eval r p`. Let me inline the left to expose the samples.
