# Tree-0.0 · turn 4 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:05:53.900Z -->

**Intent:** `commit_tactic`  
**Payload:** `swap{1} 7 -5.`

---

The view is truncated again. Let me read the full workspace view to see all the inlined code.

Now I can see the full inlined code:

Left side:
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


Right side:
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

The right side is computing discrete log values and passing them to the adversary's guess function, then checking if the adversary's output matches the random bit. On the left, the adversary receives the public key and a ciphertext, while on the right it gets group elements derived from the discrete log. The success condition compares whether the adversary's guess equals the original bit on the left, versus whether it equals the derived bit on the right.

Now I'm mapping the left and right games step by step: the initial sampling and key generation on the left correspond to the exponentiation operations on the right, the adversary's choice function receives the same type of input in both cases, and the final bit comparison needs to account for how the adversary's guess relates to the actual bit in each game. I need to clarify the operator precedence here—in EasyCrypt, exponentiation binds tighter than multiplication, so `pk0 ^ y * m` means `(pk0 ^ y) * m`, which expands to `g^(sk0*y) * m`. On the right side, I have `g^(x*y) * (if b0 then m1 else m0)`, and these match when the secret key equals the exponent and the bit and messages align across both sides. The postcondition then relates the output bit to whether the guessed bit matches the actual one.

The real problem is that the sampling order differs between the two programs—the left samples `y` after the adversary's choice and bit, while the right samples `y` before. Since `y` is independent of everything else, I can use a swap tactic to reorder the sampling and align the programs. I'm trying to figure out the correct syntax for the `swap` tactic in EasyCrypt to reorder these statements. The exact mechanics are a bit fuzzy—whether it's moving a statement to a specific position or shifting it by a certain number of positions—but the goal is to move the `y` assignment past the other deterministic operations and the `A.choose` call. Rather than getting bogged down in the swap syntax, maybe I should try a different proof strategy altogether, like using `byequiv` with `proc` and `inline` to simplify the game structure first.

Looking at what the programs look like after inlining, I can see the left side has a sequence of operations including sampling `sk0` and `y`, computing the public key and ciphertext, and calling the adversary twice. The right side is much simpler with just two random samplings. The key insight is that I need to align these programs so the sampling operations and adversary calls line up properly, then use tactics like `wp` and `rnd` to handle the deterministic and probabilistic parts.

Now I'm working through the alignment more carefully. The right program samples `x` and `y`, computes powers of the generator and their product, then calls the adversary with different inputs than the left. The final comparison `b <- b' = b0` on the right doesn't have a corresponding operation on the left after the `A.guess` call, so I need to account for that difference. My strategy is to work backwards from the bottom using `wp` to handle the postcondition, then work through the adversary call, the middle operations, and finally the initial `A.choose` call. wp` from the end.

Actually, let me try a simpler approach. The standard way to prove these equivalences in EasyCrypt for game-based crypto proofs often uses `wp` and `rnd` combined with `call` for the adversary procedures.

Let me think about this systematically. I want to show that after appropriate alignment, the left and right programs are equivalent.

The key correspondences are: sk0 on the left maps to x on the right, y stays consistent, b on the left corresponds to b0 on the right, and the public keys match up as g^sk0 = g^x. When the adversary is called with choose and guess, both sides receive the same arguments and return the same values. The ciphertext components are equal under these variable mappings, and the final comparison (b' = b) holds on both sides since the adversary's output and the challenge bit align correctly.

The real problem is that y gets sampled at different points in the execution: on the right it's sampled early before the adversary's choose call, but on the left it comes later after choose, which breaks the straightforward equivalence. and b at position 4).

I need to move y{2} down from position 2 past gx, gy, gz assignments and A.choose, or move y{1} up from position 7.

Actually, `y` on the right doesn't depend on anything before it except x (through gz later), but the sampling itself is independent. And the subsequent uses of y on the right are in:
- gy <- g ^ y (position 4)
- gz <- g ^ (x * y) (position 5)

Actually wait, gz uses both x and y. But gy and gz are just deterministic computations from x and y. And y is used later in A.guess's argument through gy and gz. So y needs to be sampled before positions 4 and 5 on the right.

Similarly on the left, y is sampled at position 7 and used at position 8 (c computation).

Let me try a different approach. I'll work backwards from the end: first use wp to push the deterministic computation down, then call A.guess, then wp again to handle the middle deterministic stuff and sampling, then call A.choose, and finally handle the remaining sampling. Looking at the right side ending with the b' assignment from A.guess and the subsequent b update, and the left side ending with b' from A.guess, I need to use wp to handle that final assignment and convert it properly. I need to reconsider the approach here. Swapping y{1} up on the left side won't work since y appears later in the computation and depends on earlier values. Let me think about moving y{2} down on the right instead, though that's also blocked because gy and gz both depend on y. I'm realizing I need a different strategy altogether—maybe I should focus on swapping y{1} to an earlier position on the left side, around position 2, to align the game structure better. I'm trying to recall the exact EasyCrypt swap syntax for moving statements around, but I'm not entirely confident about the semantics. Let me try a different approach using automated tactics instead—I'll use `wp` and a `call` tactic to handle the A.guess invocation and work backwards from there, but first I need to make sure the arguments match on both sides of the game. I'm reconsidering the approach—maybe I should just use `wp` to handle the deterministic assignments at the end, then work through the random sampling and adversary calls. Let me think about what `wp` would actually accomplish here: on the right side, the final assignment `b <- b' = b0` is deterministic, so `wp` would substitute that equality into the postcondition and simplify the weakest precondition accordingly. I'm reconsidering the approach—maybe I should use `swap` to realign the two programs, then apply `wp`, `call`, `rnd`, and `skip` tactics. The issue is that `b` gets sampled early on the left but is needed for the conditional assignment to `m`, so I can't simply move it past those computations without breaking dependencies.

Looking at both sides more carefully, the right program has a cleaner structure where the random bit and conditional are computed inline as arguments to `A.guess`, whereas the left keeps them as separate statements. Let me explore what `wp` does in pRHL and whether working backwards from the end helps align these better. from the bottom processing deterministic assignments. On the left side, the last statement is `b' <@ A.guess(c)` which is a call, so wp can't go past it. On the right side, the last is `b <- b' = b0` which is deterministic, then `b' <@ A.guess(...)` which is a call.

I think `wp` would process `b <- b' = b0` on the right, and stop at both calls. The postcondition `(b'{1} = b{1}) = b{2}` becomes `(b'{1} = b{1}) = (b'{2} = b0{2})` after substituting b{2}.

Let me look at how similar proofs handle this in the DiffieHellman library—the standard approach for cpa_ddh0 in ElGamal uses a sequence of wp, call, and rnd tactics to work through the procedures. I should try starting with wp after inlining everything, then handle the calls and random samplings. Actually, I need to think about alignment first—y is at position 7 on the left and position 2 on the right, so I should swap it up to align them before proceeding. Now I'm checking the alignment after the swap—both sides have `y <$ dt` at position 2 and the initial samplings lined up. I'm planning to work backwards from the bottom using weakest precondition reasoning: handling the final comparison, calling the adversary's guess, managing the deterministic steps between the choose and guess calls, sampling the boolean, then the choose call, and finally the random samplings. Let me test `swap{1} 7 -5.` to see if this reordering works.

Actually, I need to verify whether `y <$ dt` can move past the `A.choose(pk)` call—since the sampling doesn't affect the global state and the adversary can't read y, they should be independent, so the swap tactic should handle this. Let me try it and see what happens. I need to reconsider the alignment strategy. Moving y up to position 2 on the left side would help align it with where y is used in the deterministic assignments on the right, but the issue is that y gets sampled after the adversary's choice and the bit selection on the left, while it's needed earlier on the right for those assignments. Let me trace through what the programs would look like after the swap to see if there's actually a way to make them align properly.

Looking at the bottom of both programs, the right side ends with a deterministic assignment that compares the adversary's guess to the original bit, while the left side ends with the adversary's guess call itself. I should use the weakest precondition calculation to handle these deterministic assignments at the end.

Actually, let me step back and try a more direct approach using EasyCrypt's swap tactic. Since y doesn't depend on b, the public key choice, or the message selection, I should be able to move it past all those operations to an earlier position in the program.

Let me start simple and just apply `wp` to handle the deterministic statements first, then see what the remaining goals look like.
