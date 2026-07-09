# Tree-0.0 · turn 6 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:06:53.473Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={glob A}).`

---

The view looks similar but truncated. Let me read the full view to see what happened.

`wp` handled the `b <- b' = b0` assignment on the right side. Now the postcondition is `(b'{1} = b{1}) = (b'{2} = b0{2})`.

The programs are now:

Left:
1. sk0 <$ dt
2. y <$ dt
3. (pk, sk) <- (g ^ sk0, sk0)
4. (m0, m1) <@ A.choose(pk)
5. b <$ {0,1}
6. pk0 <- pk
7. m <- if b then m1 else m0


8. c <- (g ^ y, pk0 ^ y * m)
9. b' <@ A.guess(c)

Right:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)
6. (m0, m1) <@ A.choose(gx)
7. b0 <$ {0,1}
8. b' <@ A.guess(gy, gz * if b0 then m1 else m0)

Post: (b'{1} = b{1}) = (b'{2} = b0{2})

Now I need to apply the `call` rule to handle the adversary's guess queries.

For the A.guess calls, I need to establish a relational invariant connecting both sides. On the left, the adversary receives `(g ^ y, pk0 ^ y * m)`, while on the right it receives `(gy, gz * if b0 then m1 else m0)`. I need to verify these arguments are equivalent under the invariant, then after the call completes, the results should satisfy `b'{1} = b'{2}`. I'm noticing a discrepancy in how A.guess is being called on each side. On the left, it receives a single `ctxt` argument (which is a tuple of two group elements), but on the right it appears to be called with two separate arguments instead of a tuple, which would be a type mismatch I need to resolve. For the second condition to hold, I need `sk0 * y` to equal `x * y`, which means `sk0` must equal `x` — but that's the discrete log relationship I'm trying to prove from the DDH assumption, so this approach won't work directly.

Let me reconsider the strategy: I'll call the adversary to get their guess, use weakest precondition reasoning to handle the deterministic steps between the choose and guess phases, then apply randomness reasoning for the challenge bit `b` versus `b0`, continue through the middle computations, call the adversary again for their choice, apply weakest precondition to the final deterministic operations, and finally use randomness reasoning for the exponent `y`.

Now I'm working through the remaining steps: randomness for `sk0` and `x`, then finishing with skip and progress tactics.

I need to verify the correct EasyCrypt syntax for the call tactic—specifically whether `call (_: ={glob A})` is the right form, which would establish that the global state of adversary `A` remains equal before and after the call while also ensuring the arguments and results match. I need to see the next thinking to rewrite it. Could you provide the next thinking chunk that follows the current rewritten thinking?
