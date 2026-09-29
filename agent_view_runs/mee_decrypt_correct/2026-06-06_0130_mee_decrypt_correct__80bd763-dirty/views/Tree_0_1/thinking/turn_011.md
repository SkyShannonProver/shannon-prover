# Tree-0.1 · turn 11 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:39:31.906Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ mk = _mk /\ p = None).`

---

"invalid last instruction" — this means the `while` tactic requires the while loop to be the LAST (and only) remaining statement. Since there's code after the while loop (the unpad + if/MAC), the tactic fails.

I need to use `seq` to cut the code into: (1) the while loop, and (2) the post-loop code. Then I can apply `while` on part (1) and handle part (2) separately.

The `seq` tactic in phoare mode: `seq N : (MIDCONDITION).` where N is the statement number to cut after.

After `sp.`, the while loop is statement 1. 

So I need `seq 1 : (MID).` where `MID` captures what we know after the while loop completes — that the padding has been decrypted, the plaintext is still None, and the key and ciphertext variables remain unchanged. This will split the proof into two parts: one handling the while loop itself, and another for the remaining unpad and MAC verification code. After the while loop exits, I know that `i >= size c`, and combined with the loop invariant `i <= size c`, this means `i = size c`. From the invariant at this point, `padded` equals the result of decrypting with the full ciphertext, and the other variables match their initial values.

For the midcondition after the loop, I need `padded`, `p = None`, and `mk` since those are used in the subsequent code, while variables like `ek`, `c`, `i`, and `s` aren't referenced afterward. Let me verify whether `mk` is actually a program variable by checking the context. I'm reconsidering the overall proof structure—maybe I should undo the `sp.` tactic and use `conseq` instead to restructure things more carefully. The key is handling the setup assignments, the while loop with its call, and the post-loop code, so I'll need to break this down systematically with `seq` to handle each piece. Testing this approach...
