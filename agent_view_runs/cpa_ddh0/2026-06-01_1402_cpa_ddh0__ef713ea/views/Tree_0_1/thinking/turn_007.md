# Tree-0.1 · turn 7 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:07:53.295Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

The `call (_: true)` was accepted. Let me read the full view to see the updated postcondition and remaining code.

Now I can see the postcondition after `call (_: true)`:

```
post =
  (c{1} = (gy{2}, gz{2} * if b0{2} then m1{2} else m0{2}) /\
   (glob A){1} = (glob A){2} /\ true) &&
  forall (result_L result_R : bool) (A_L A_R : (glob A)),


```

The forall constraint requires that when the left and right results are equal and their global state matches, the comparison of each result against its respective boolean value must also be equal. This boils down to needing `b{1} = b0{2}` to hold.

For the actual programs, I'm laying out what happens on the left side: the adversary samples a secret key, derives the public key pair, gets the two messages from the adversary's choice function, samples a random exponent and bit, sets up the public key reference, and then constructs the challenge ciphertext with the exponentiated group element and the masked message.

On the right side, the process is similar but structured differently: sampling both exponents upfront, computing their powers and product in the group, then having the adversary choose based on the first exponent's group element, and finally sampling the challenge bit.

Now I need to apply the weakest precondition calculation to work through the deterministic assignments on the left side—specifically the ciphertext, message selection, and public key reference—and substitute these into the postcondition to see how they align with the right side's structure. And on the RHS: gx, gy, gz are computed before A.choose, so wp would process what's after A.choose... actually gy and gz are before A.choose on the RHS.

Hmm, let me think. `wp` processes deterministic statements from the END of both programs simultaneously. 

LHS ends with: `c <- (g^y, pk0^y * m)` — deterministic
Then `m <- if b then m1 else m0` — deterministic
Then `pk0 <- pk` — deterministic
Then `b <$ {0,1}` — random sampling, wp stops here

RHS ends with: `b0 <$ {0,1}` — random sampling, wp stops here (or maybe even nothing to process)

So wp processes deterministic statements from both ends until hitting a random sampling. The RHS has no deterministic tail, so wp would only work through the LHS's deterministic statements before the `b` sampling. Let me just try applying wp and see what happens.
