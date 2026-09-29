# Tree-0.1 · turn 12 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:09:52.063Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

Let me read the full view to see the full postcondition.

Now I can see the state:

Programs:
LHS:
1. sk0 <$ dt
2. (pk, sk) <- (g ^ sk0, sk0)
3. y <$ dt

RHS:
1. x <$ dt
2. y <$ dt

The wp only processed the RHS assignments (gx, gy, gz) but NOT the LHS assignment `(pk, sk) <- (g^sk0, sk0)`. That's interesting. Let me check — the post says `pk{1}` is still a variable, but there's still a `(pk, sk) <- (g^sk0, sk0)` in the code. 

Ah, I see what's happening — wp processes deterministic statements working backwards from the end. On the LHS, it hits the random sampling `y <$ dt` at the bottom and stops there, so it never reaches the earlier assignment. On the RHS, all the final statements are deterministic exponentiation operations, so wp processes through them until it encounters the random sampling.

Now I need to figure out how to match the samplings between the two sides. The LHS has `sk0 <$ dt`, then a deterministic assignment for `(pk, sk)`, then `y <$ dt`. The RHS just has `x <$ dt` followed by `y <$ dt`. Since they're not perfectly aligned — the LHS has that extra deterministic step in between — I should try using `rnd` to match the final `y` samplings on both sides, then use wp to absorb the `(pk, sk)` assignment, and finally use `rnd` again to match `sk0` with `x`.
