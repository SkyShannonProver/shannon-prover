# Tree-0.1 · turn 5 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:06:43.094Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

The swap was accepted. Now y is at position 4 in the LHS. Let me read the full view to confirm.

Actually, I can see from the preview that y is now at position 4 on the LHS (after A.choose). Good.

Now the programs are:
LHS:
1. sk0 <$ dt
2. (pk, sk) <- (g ^ sk0, sk0)
3. (m0, m1) <@ A.choose(pk)


4. y <$ dt
5. b <$ {0,1}
6. pk0 <- pk
7. m <- if b then m1 else m0
8. c <- (g ^ y, pk0 ^ y * m)
9. b' <@ A.guess(c)

RHS:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)
6. (m0, m1) <@ A.choose(gx)
7. b0 <$ {0,1}
8. b' <@ A.guess(gy, gz)
9. if b0 then m1 else m0)
10. b <- b' = b0

I see the issue now—y needs to align across both sides, but on the RHS it's sampled early while gy and gz depend on it. Rather than trying to shuffle everything around to match positions perfectly, I should use weakest precondition reasoning to work backwards from the tail, then handle the randomness and function calls step by step.

Let me start with `wp` on the deterministic assignments at the end. The RHS has `b <- b' = b0` which is deterministic, but the LHS has `b' <@ A.guess(c)` which is a call—so `wp` would only apply to the RHS portion. Before that call on the LHS, there are deterministic steps like computing `c`, `m`, and `pk0` that I need to account for separately.

After applying `wp` to the RHS's final assignment, both sides end up with calls to `A.guess`, just with different arguments—the LHS calls it with `c` while the RHS calls it with the expanded form. This means I can use `call (_: true)` to match them, but I need to verify the arguments align correctly after the postcondition is updated. For the call to work, A.guess needs to receive equal arguments on both sides. On the left I have the context `c` as a pair of group elements, while on the right I'm constructing a similar pair from the computed values. I need to verify that these arguments match up: the first components should be equal (both `g^y`), and the second components should also be equal (both `pk0^y * m`).

Substituting in what I know about `pk0` and `m` from the left side, I can expand the second component and see what constraints this imposes. The equality requires that several values match across the two sides: the exponent `y` must be the same, the secret key component `sk0` on the left must equal the exponent `x` on the right, the bit `b` must match `b0`, and the message values `m0` and `m1` must be consistent.

My approach is to work backwards from the `A.guess` call—first handling the deterministic tail with `wp`, then matching the guess itself, then using `wp` again to verify the deterministic assignments that set up the preconditions. Before I can match `A.guess`, I need to establish that all its arguments are equal and that the global state `A` is the same on both sides.

Looking at what happens before `A.guess` is called on the left side, I'm tracing through the sequence of operations: sampling `sk0`, deriving the public key and secret key pair, calling `A.choose` to get the messages, sampling the exponent `y`, and sampling the bit `b`.

On the right side, the setup is different—I'm sampling `x` and `y` directly, computing the group elements `gx`, `gy`, and `gz`, then calling `A.choose` with `gx` instead of the derived public key.
