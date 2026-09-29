# Tree-0.0 · turn 2 · commit_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:31:21.598Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Good. The procedure body after `proc.` shows a deterministic decryption:

1. `p <- None`
2. `(ek, mk) <- key`
3. `s <- head witness c`
4. `c <- behead c`
5. `padded <- []`
6. `i <- 0`
7. While loop doing CBC decryption block by block
8. `pt <- unpad padded`
9. If `pt <> None`, verify MAC and set result

The postcondition requires `p = mee_dec AESi hmac_sha256 _ek _mk (head witness _c) (behead _c)`.
Now I'm thinking through the proof strategy for this phoare goal with bound `[=] 1%r`. Since the procedure is deterministic, I'll need to use `proc` to enter, then `sp` and `wp` to handle the assignments, construct a loop invariant for the while loop, process the conditional branch, and reason about the calls to the PRP oracle and MAC verification. I think the simpler approach is better — I'll start with `proc.`, then inline all the procedure calls to eliminate the complexity of handling `PseudoRP.fi` and `MAC.verify` separately. After that, I can use `wp` to work backwards from the end of the function, handle the while loop with an appropriate invariant, and then process the prefix with `sp` before closing out the proof.
