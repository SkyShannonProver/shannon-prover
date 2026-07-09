# Tree-0.1 · turn 4 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:05:59.683Z -->

**Intent:** `commit_tactic`  
**Payload:** `swap{1} 7 -3.`

---

The view is truncated again. Let me read the full workspace view to see the complete inlined code on both sides.

Now I can see the full inlined code on both sides:

LHS:
```
sk0 <$ dt
(pk, sk) <- (g ^ sk0, sk0)
(m0, m1) <@ A.choose(pk)
b <$ {0,1}
pk0 <- pk
m <- if b then m1 else m0
y <$ dt
c <- (g ^ y, pk0 ^ y * m)
b' <@ A.guess(c)


```

RHS:
```
x <$ dt
y <$ dt
gx <- g ^ x
gy <- g ^ y
gz <- g ^ (x * y)
(m0, m1) <@ A.choose(gx)
b0 <$ {0,1}
b' <@ A.guess(gy, gz * if b0 then m1 else m0)
b <- b' = b0
```

post = (b'{1} = b{1}) = b{2}

I need to align these two programs and figure out the mapping between them. The key difference is that the RHS samples both x and y upfront, computes their exponentials and product, then uses those in the adversary calls, while the LHS derives everything from sk0 and y. Let me work through how the variables correspond...

The postcondition `(b'{1} = b{1}) = b{2}` tells me I need to show that the first component of b' equals the first component of b, and this equivalence holds in the second component. On the RHS, b is defined as `b' = b0`, so I need to establish that `b'{1} = b{1}` and `b0{2}` match up appropriately.

My strategy is to use program equivalence tactics like `swap` to reorder the statements, then apply `wp` to reason about weakest preconditions, `rnd` for randomness, and `call` for the adversary invocations to show the two sides produce equivalent results. I need to think through how the weakest precondition operator handles these two programs—the RHS has that extra deterministic assignment at the bottom that the LHS doesn't, so I need to figure out how to process them together. The postcondition simplifies based on what `b{2}` equals after that final assignment. Let me reconsider whether `wp` processes both sides simultaneously or if I should try a different tactic like using `swap` to realign the programs first.

Looking at the actual statements in each program, the LHS and RHS have their operations in different orders—the LHS places `y` after `b`, while the RHS has `y` earlier, and there's that extra assignment `b <- b' = b0` on the RHS at the end. I think the best strategy is to use `swap` to reorder statements on the LHS so they match the RHS's structure more closely, which should make the proof easier to handle. I'm realizing the core problem: y is sampled independently, so it should be movable, but in pRHL I can't easily swap it past the adversary's procedure calls like A.choose. The real challenge is that on the LHS, y comes after A.choose is called, while on the RHS it comes before, and rearranging past these calls requires more sophisticated tactics than simple swaps. EasyCrypt pRHL, `swap{2} 2 4` should be able to move `y <$ dt` past the deterministic assignments (gx, gy, gz) and the procedure call. I think EasyCrypt's `swap` is more flexible in what it can move past, as long as there are no data dependencies.

But `gy <- g ^ y` and `gz` don't depend on y... wait, `gy <- g ^ y` DOES depend on y! And `gz <- g ^ (x * y)` also depends on y. So we can't move y past those assignments.

OK so the programs have fundamentally different orderings that can't be easily reconciled with swap alone.

Let me try a different approach: use `wp` and `auto` more aggressively.

Actually, I think the right approach is to use a swap that moves the random sampling up by three positions, placing it right after the initial choice. This works because the random variable doesn't depend on any of the intermediate assignments like b, pk0, or m, and those assignments don't depend on the random variable either. I think the standard EasyCrypt approach would be to use `wp` to handle the deterministic tail statements, then work backwards through the randomized assignments and procedure calls. The key issue is that the two programs aren't aligned—on the left side `y` is sampled after `b` and the `A.choose` call, but on the right it comes before. I need to swap those statements first using a position-based swap command to realign them.

Let me recount the actual line positions after inlining to figure out the correct swap indices, since the numbering determines which statements I'm moving. Looking at the structure, both sides have 9 numbered statements arranged symmetrically. For the swap tactic, I need to move statement 7 (the `y` sampling) backward by 3 positions to position 4, which is valid since `y` doesn't depend on the `b` assignment that comes after it. are m, pk0, and b — none of which depend on y or affect its value. So moving y up by three positions should be valid. After the swap, y gets sampled right after the A.choose call, then b is sampled, followed by the conditional assignment to pk0 and m, with the ciphertext computation coming after.

On the RHS, I'm working through a different structure: sampling x and y, computing g^x and g^y, then g^(x*y), using those to call A.choose and A.guess with a conditional message selection based on b0, and finally checking if b' equals b0.

Now I'm working backwards from the end to apply the weakest precondition. The LHS ends with a call to A.guess, while the RHS ends with a deterministic assignment b <- b' = b0, so wp only processes the RHS's final statement, substituting that equality into the preceding context.

After substitution, the postcondition becomes (b'{1} = b{1}) = (b'{2} = b0{2}), and I'm considering whether the LHS's deterministic assignment c <- (g ^ y, pk0 ^ y * m) can also be processed by wp. Let me try using swap{1} 4 3 to rearrange the statements and see if that helps align the structure better.

Actually, moving b <$ {0,1} forward creates a dependency problem since m depends on b being sampled first. Maybe I should try a different tactic entirely—perhaps using auto or sim to handle the weakest precondition and randomness automatically rather than manually manipulating the statement order.

Let me just attempt `swap{1} 7 -3` to move statement 7 up three positions to where statement 4 currently is, which would put the random sampling y <$ dt before the conditional assignment. If that doesn't work, I'll explore other approaches.
