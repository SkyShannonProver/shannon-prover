# Tree-0.1 · turn 8 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:08:17.957Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

The postcondition is truncated. Let me read the full view.

Now I can see the full state. The programs remaining are:

LHS:
1. sk0 <$ dt
2. (pk, sk) <- (g ^ sk0, sk0)
3. (m0, m1) <@ A.choose(pk)
4. y <$ dt
5. b <$ {0,1}

RHS:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x


4. gy <- g ^ y
5. gz <- g ^ (x * y)
6. (m0, m1) <@ A.choose(gx)
7. b0 <$ {0,1}

The postcondition checks that the masked message values match between the two games and that the adversary's global state remains synchronized, with the equivalence holding across all possible adversary outcomes.

Now I need to establish the correspondence between the left and right game instances: b{1} maps to b0{2}, y{1} to y{2}, sk0{1} to x{2}, and the adversary's choice function applied to pk{1} = g^sk0{1} must align with A.choose(gx{2}) where gx{2} = g^x{2}.

After applying the `rnd` tactic to match the random samplings of b and b0 from {0,1}, both sides are left with deterministic computations on the RHS before reaching the final A.choose call, so I need to handle those assignments next. I'm applying the `rnd` tactic to handle the randomness in both branches, starting with the shared random sampling steps.
