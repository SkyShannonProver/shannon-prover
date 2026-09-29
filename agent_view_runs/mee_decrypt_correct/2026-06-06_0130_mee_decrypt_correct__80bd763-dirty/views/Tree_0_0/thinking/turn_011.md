# Tree-0.0 · turn 11 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:35:34.198Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp.`

---

Good. The phoare while form is:
```
while (INVARIANT) (VARIANT).
```

No probability argument — just invariant and variant.

Now let me think about the overall proof plan:

The procedure is:
```
p <- None
(ek, mk) <- key
s <- head witness c
c <- behead c
padded <- []
i <- 0
while (i < size c) {
    ci <- nth witness c i
    pi <@ PRPc.PseudoRP.fi(ek, ci)
```

Continuing with the loop body, I accumulate the padded values by subtracting each pseudorandom output from the current state, then update the state and increment the counter. After the loop, I unpad the accumulated values and verify the MAC if unpadding succeeds, setting the result to the decrypted plaintext only if verification passes.

Now I need to unfold what `mee_dec` actually computes to establish the postcondition.

Unfolding the definition...

```
cbc_dec Pi k st c =
  with c = [] => []
  with c = ci :: c => let pi = Pi k ci in (pi +^ st) :: (cbc_dec Pi k ci c)
```

So the loop needs to compute `padded = cbc_dec AESi _ek (head witness _c) (behead _c)` by iterating through the ciphertext blocks, applying the block cipher and XORing with the previous state. The loop invariant tracks that after processing `i` blocks, we've accumulated the correct decrypted values up to that point.

In the loop body, I'm extracting the i-th ciphertext block, applying the AES decryption, and XORing with the current state value. Since subtraction in this boolean ring is the same as XOR (because negation is identity), `s - pi` equals `s +^ pi`. Then I update the state to the current ciphertext block for the next iteration.

This is exactly computing CBC decryption: each plaintext block is the XOR of the AES-decrypted ciphertext with the previous ciphertext block (or IV for the first block). So the loop invariant tracks that `padded` accumulates the result of applying CBC decryption to the first i blocks.

Now I need to carefully trace through the variable assignments. After step 4, `c` gets reassigned to `behead _c`, so it no longer holds the original ciphertext argument. At loop entry, `ek` and `mk` are the key components, `s` is initialized to the IV (the head of the original ciphertext), and the loop iterates over the tail of the ciphertext. In each loop iteration, I'm computing the AES-encrypted value of the current ciphertext block, then XORing it with the previous state to build up the padded output array. After k iterations, the padded array contains the sequence of XOR results where each element combines the previous state with the AES encryption of the corresponding ciphertext block.

I can express this as a loop invariant: the padded array at iteration i equals the CBC decryption of the first i ciphertext blocks, and the state s tracks the last ciphertext block processed. When the loop terminates after processing all blocks, the padded array holds the complete CBC decryption result.

Now I'm sketching out the proof strategy: first establish the initial conditions before the loop, then verify the loop invariant holds through each iteration using the pseudorandom function call, and finally handle the unpadding and MAC verification after the loop completes.

The tricky part is dealing with the `PseudoRP.fi` call inside the loop body—in phoare logic, weakest precondition can't pass through function calls, so I need to use `ecall` with a specification that captures the result as the AES encryption of the key and ciphertext block.

Let me try a more direct approach and just run `sp` to see how far it gets with the initial assignments before hitting the loop.
