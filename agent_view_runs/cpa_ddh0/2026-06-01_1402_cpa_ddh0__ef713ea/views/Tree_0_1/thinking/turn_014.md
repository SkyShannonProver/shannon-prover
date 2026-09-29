# Tree-0.1 · turn 14 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:10:06.898Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

Now both sides have just one sampling each:
LHS: sk0 <$ dt
RHS: x <$ dt

And `pk_L = g ^ sk0{1}` is substituted in the postcondition. Now I match sk0 with x using `rnd`.
