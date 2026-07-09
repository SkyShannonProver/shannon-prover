# Tree-0.0 · turn 33 · probe_tactic

<!-- session 04f2da79-838f-426c-bf2c-64746dff5b0e · 2026-06-10T21:54:39.950Z -->

**Intent:** `probe_tactic`  
**Payload:** `while{2} (0 <= i{2} <= size ns{2}) (size ns{2} - i{2}).`

---

Let me read `GenChaChaPoly`, `CCRO`, and the `FinRO`/`RO.get` semantics to resolve the domain question.

Now I understand the RO-domain subtlety: `GenChaChaPoly(CCRO(FinRO))` populates `RO.m` at `(n,0)` on every dec query, so domain coverage holds at the game level — but it is NOT exposed by `UFCMA_genCC`'s postcondition. Let me empirically test the loop structure rather than simulate. First, confirm the one-sided `while` form with a minimal invariant.
