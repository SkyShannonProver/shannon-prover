# Tree-0.1 · turn 11 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:09:25.319Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Let me read the full view.

Good. Now the remaining programs are:

LHS:
1. sk0 <$ dt
2. (pk, sk) <- (g ^ sk0, sk0)
3. y <$ dt

RHS:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)

The postcondition is complex but reduces to:
1. `pk{1} = gx{2}` → `g^sk0{1} = g^x{2}` → `sk0{1} = x{2}`


2. The global state must match between both sides, and since the adversary gets the same result from both, I have `m0{1} = m0{2}` and `m1{1} = m1{2}`.
3. For the final output, I need `g^y{1} = gy{2}` and `pk{1}^y{1} = gz{2}`, which means `g^(x{2}*y{2})` must equal the left side's computation.
4. The key insight is that if `sk0{1} = x{2}` and `y{1} = y{2}` both come from the same distribution, then the exponents match up perfectly: `g^(sk0{1}*y{1}) = g^(x{2}*y{2})`. Now I need to trace through the deterministic assignments on the right side—specifically how `gx`, `gy`, and `gz` are computed—and verify they align with the left side's samplings.

I'll use the weakest precondition tactic to absorb all the deterministic steps. After applying `wp`, the left side reduces to just sampling `sk0` and `y` from the distribution, while the right side samples `x` and `y`. The deterministic computations like `pk = g^sk0` get substituted directly into the postcondition, leaving me with a cleaner equivalence to verify.
