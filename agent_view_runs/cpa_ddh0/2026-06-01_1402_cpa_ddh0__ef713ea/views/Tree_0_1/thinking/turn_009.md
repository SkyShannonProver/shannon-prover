# Tree-0.1 · turn 9 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:08:51.175Z -->

**Intent:** `commit_tactic`  
**Payload:** `swap{1} 4 -1.`

---

The postcondition is truncated. Let me read the full view.

Now I see the full state. After matching b with b0 (both unified to `bL`), the remaining programs are:

LHS:
1. sk0 <$ dt
2. (pk, sk) <- (g ^ sk0, sk0)
3. (m0, m1) <@ A.choose(pk)
4. y <$ dt

RHS:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y


5. gz <- g ^ (x * y)
6. (m0, m1) <@ A.choose(gx)

Now I'm checking the postcondition to verify the equivalence holds after these additional computations on the right side, ensuring the challenge values and message selections align properly. I'm looking at what needs to hold for both sides to match up. The key constraints are that `y` values must be equal, the `pk` and `gz` terms need to align through the group algebra, the message choices must be identical, and the global state must match. Both sides eventually call the same choice function, but the LHS has different state going in—specifically `sk0` and the `(pk, sk)` pair—compared to what the RHS has. I'm noticing the positions don't align for a direct `call` match—the LHS has `y <$ dt` after A.choose while the RHS ends with A.choose. I need to reorder the LHS first by moving that `y <$ dt` statement before A.choose, assuming it doesn't depend on the result from A.choose.
