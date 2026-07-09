# Tree-0.1 · turn 13 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:10:00.601Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Now the remaining programs are:
LHS: sk0 <$ dt; (pk, sk) <- (g^sk0, sk0)
RHS: x <$ dt

I need to absorb the (pk, sk) assignment with `wp`, then `rnd` to match sk0 with x, then `skip` and close.

Let me do `wp.` next.
