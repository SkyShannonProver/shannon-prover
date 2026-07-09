# Tree-0.0 · turn 12 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:37:14.106Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline MEEt.PRPc.PseudoRP.fi.`

---

`sp.` processed the 6 prefix assignments and now the precondition has:
```
exists (c0 : block list),
  p = None /\
  (ek, mk) = key /\
  s = head witness c0 /\
  c = behead c0 /\
  padded = [] /\ i = 0 /\ (key, c0).`1 = (_ek, _mk) /\ (key, c0).`2 = _c
```

Good. Let me commit this and then think about the next step.
Actually, I should reconsider this approach. The existential quantifier on `c0` makes things a bit unwieldy, and I notice there's redundancy here—since `(ek, mk) = key` and `(key, c0).`1 = (_ek, _mk)`, I can simplify by substituting to get `ek = _ek`, `mk = _mk`, and `c0 = _c`, which cleans up the precondition considerably.

Now I'm thinking about the while loop and what invariant it needs to maintain. The loop performs CBC decryption, so the invariant should capture that `padded` accumulates the decrypted blocks as we iterate through the ciphertext, with `s` tracking the state between iterations and `i` counting how many blocks we've processed so far. I'm working through the CBC decryption function to understand how the state evolves as we process each ciphertext block. The function chains the decryption of each block, using the previous ciphertext block as the state for XORing with the next decrypted block. So as we iterate through the ciphertext blocks, the state variable tracks the last processed ciphertext block, and the padded output accumulates the decrypted blocks XORed with their respective states.

Now I'm noticing that in the loop body, the program computes `s - pi` where `pi` is the AES decryption result, and in the boolean ring, subtraction is the same as XOR since negation is the identity. So `s - pi` becomes `s +^ AESi ek ci`, which matches exactly what the `cbc_dec` function produces.

For the loop invariant, I need to capture that after `i` iterations, `padded` contains the decrypted ciphertext blocks and `s` tracks the previous ciphertext block—which is either the initial value for `i = 0` or the `(i-1)`-th ciphertext block for `i > 0`. The state after processing the first `i` ciphertext blocks is exactly the last ciphertext block seen, or the initial state if none were processed yet—so `s = last st (take i c)` captures this. Now I need to handle the call to `PRPc.PseudoRP.fi` inside the loop, which requires proving the loop body as a phoare goal and providing a spec for that call. I'm realizing `wp` won't work across the `if` block or the function call inside it, so I need a different strategy. The `mee_correct` lemma shows the functional specification pattern, but I should try using `conseq` to restructure the goal instead.

In EasyCrypt, a phoare statement like `phoare [M.f : P ==> Q] = 1%r` means the probability of reaching Q is 1 whenever P holds. I could try using `conseq` to transform this into a Hoare triple, though I'm not sure if that's the right approach here.

Looking at the actual error from `hoare.`, the first goal shows a false side condition `0%r = 1%r`, which arises because `hoare.` assumes procedure calls have probability 0 in the worst case. Since my code calls `PRPc.PseudoRP.fi` and `MAC.verify`, those contribute to making the overall probability 0, which creates this contradiction.

The fix is to provide losslessness proofs for these called procedures. Though `PseudoRP.fi` is likely just a wrapper around the underlying PRP (and should be lossless), EasyCrypt can't inline abstract or functor-instantiated procedures, so it needs explicit probability specs to know they terminate with probability 1. Looking at the phoare specification, I can see the module path structure: `MEEt.PRPc.PseudoRP`, where `PRPc` is a sub-theory within `MEEt` and `PseudoRP` is the module inside it that provides the block cipher operations for the decryption correctness proof.

Let me try a different proof strategy using `ecall` to handle the function calls with their phoare specs, then work backwards through the proof structure to handle the unpadding, MAC verification, and conditional logic that determines the final decryption result. I'm stepping back from the complex approach and trying something simpler — just committing the current state and building a while loop directly. The key insight is handling the call inside the loop body using phoare's `call` tactic, which takes a phoare spec to establish what the function does in this context.

Looking at how `PseudoRP.fi` is typically structured, it's just a simple return statement wrapping the underlying function, so if I could inline it, the loop body would reduce to a straightforward assignment. The challenge is that inlining doesn't work here for some reason, so I need to work with the call as-is. The `inline *` rejection and the "unknown procedure" error from `inline PseudoRP.fi` suggest different issues — maybe `inline *` found nothing to inline, while the qualified name was just wrong. Let me try using the full path `inline MEEt.PRPc.PseudoRP.fi` instead.
