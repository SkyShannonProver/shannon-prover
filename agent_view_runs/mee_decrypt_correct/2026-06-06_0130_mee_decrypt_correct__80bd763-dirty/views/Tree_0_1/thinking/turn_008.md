# Tree-0.1 · turn 8 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:35:01.740Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp.`

---

Good, `sp.` was accepted. After `sp.`, the precondition now has the initial assignments pushed in:
```
pre =
  exists (c0 : block list),
    p = None /\
    (ek, mk) = key /\
    s = head witness c0 /\
    c = behead c0 /\
    padded = [] /\ i = 0 /\ (key, c0).`1 = (_ek, _mk) /\ (key, c0).`2 = _c
```

And the remaining program is the while loop + post-loop code.
I'm reconsidering the approach here. The existential in the precondition is getting unwieldy, so maybe I should try working backwards from the end instead—using `wp` to handle the post-loop code and while loop. But that won't work either since `wp` can't push past the MAC.verify procedure call. Let me step back and think about this differently before committing to `sp.`.

The real structure I need to capture is that the while loop computes CBC decryption, then unpadding extracts the message and tag, and finally the if branch verifies the MAC against the functional specification `mee_dec`, which chains these operations together in sequence. and the loop invariant needs to account for the fact that `s` tracks the previous ciphertext block, starting as the IV. After the loop terminates with `i = size c`, the padded result should equal the full CBC decryption of the ciphertext `behead _c` using the initial IV `head witness _c` and key `_ek`. Looking at how `cbc_dec` works, I can see that each decrypted block depends on the previous ciphertext block as the IV for the next iteration. In the loop, we're computing `s +^ pi` where `s` is the previous ciphertext block (or initial IV), and `pi` is the decrypted current block — the subtraction operation in this boolean ring context is equivalent to XOR. So in the ring instance, subtraction becomes XOR since the additive inverse is the identity function. That means `s - pi` simplifies to `s +^ pi`, which matches what `cbc_dec` computes due to XOR's commutativity. Now I need to formalize the loop invariant that tracks the decryption progress through the ciphertext blocks.

The key insight is that `s` represents the previous ciphertext block (or the IV on the first iteration), so after `i` iterations, `s` should be either the IV if we haven't started yet, or the `i-1`th ciphertext block otherwise. I'm realizing this approach is getting tangled, so let me try something more direct—maybe using `conseq` to simplify the postcondition and then applying `auto` with the right lemmas. I should look at how `mee_correct` handles similar situations to see if there's a useful pattern I can apply here. I'm thinking through the proof structure for the phoare judgment. The program has setup assignments, a while loop that calls into the pseudorandom function, and then post-loop operations with unpadding and MAC verification. For the `[=] 1%r` proof, I need to handle the while loop with an invariant and termination variant, then decide whether to inline the function call or work with it directly inside the loop.

Let me reconsider the tactic approach—maybe `wp` working backward from the end would be more effective than pushing forward with `sp`, since `wp` can handle the post-loop operations but will stop at procedure calls. I could also try using `seq` to split the program at strategic points. I'm wondering if `inline` might only work on the first call in the program text, and since the `PRPc.PseudoRP.fi` call is nested inside the while loop body, it might not be directly accessible until we enter that loop. Let me think about what `wp.` would accomplish after committing `sp.` — it should push backwards through the deterministic assignments after the loop, working through the unpadding and the conditional MAC verification.

Maybe the right strategy is to handle the post-loop code separately with a `seq` cut, or try a simpler approach using `wp` combined with call handling and skip tactics. The core challenge is figuring out how to manage the while loop invariant and the calls within the loop body. loop is at the head of the program. If there's code after the while loop, I might need to handle that differently — maybe the postcondition subgoal will contain the remaining code, or I need to structure the proof differently to account for what comes after.

Let me try a different approach: instead of `sp.` followed by `while`, I could use `wp.` to work backwards from the end, which would absorb the deterministic assignments and stop at procedure calls or loops. That way I can understand the structure better before committing to a particular tactic sequence. I'm working through how the weakest precondition operator interacts with this code structure. The `wp.` tactic can absorb the final assignment on line 9.3, folding it into the postcondition, but it seems to stop when it encounters the MAC.verify call since that's an external function call. I'm uncertain whether `wp` can cross the `if` statement boundary, so I should test this empirically rather than reason about it abstractly. Let me try committing to the `sp.` tactic first, then experiment with different approaches like using `ecall` to handle the MAC.verify invocation directly. pose this into a hoare triple plus termination. Let me try `hoare.` as a tactic, or maybe `byphoare` or `bypr`. Actually, since this program is completely deterministic with no random sampling, the phoare judgment should really just reduce to a hoare triple. Let me be more aggressive and try `wp.` directly from the full procedure body without committing `sp.` first to see what happens.
