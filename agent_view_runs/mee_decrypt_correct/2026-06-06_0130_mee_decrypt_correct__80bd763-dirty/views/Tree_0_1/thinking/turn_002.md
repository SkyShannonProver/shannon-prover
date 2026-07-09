# Tree-0.1 · turn 2 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:31:18.887Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Good, `proc.` is accepted. The procedure body shows:

1. `p <- None`
2. `(ek, mk) <- key`
3. `s <- head witness c`
4. `c <- behead c`
5. `padded <- []`
6. `i <- 0`
7. A while loop: `while (i < size c) { ... }` that does CBC decryption
8. `pt <- unpad padded`
9. An if branch checking `pt <> None`, doing MAC verify

The postcondition is `p = mee_dec AESi hmac_sha256 _ek _mk (head witness _c) (behead _c)`.
Now I'm planning the proof strategy: I'll use `proc` to enter, then `sp` and `wp` for the assignments, establish a loop invariant for the CBC decryption while loop, handle the calls to the PRP and MAC verification, and finish with automation. that the procedure deterministically computes the functional spec since all operations are deterministic with no random sampling. The main challenge is establishing loop invariants for the CBC decryption while loop, handling the AES inverse function call, and verifying the MAC computation matches the functional specification.
