# Tree-0.1 · turn 26 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:45:18.442Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

`wp.` was accepted and pushed backward through the post-call assignments (lines 3-5: `padded <- padded ++ [s - pi]; s <- ci; i <- i + 1`). Now the remaining program is just:

```
(1) ci <- nth witness c i
(2) pi <@ PRPc.PseudoRP.fi(ek, ci)
```

And the postcondition has been updated with the substitutions from lines 3-5:
```
post =
  let i0 = i + 1 in
  (0 <= i0 /\
   i0 <= size c /\
   padded ++ [s - pi] = cbc_dec AESi ek (head witness _c) (take i0 c) /\
   ci = last (head witness _c) (take i0 c) /\
   p = None /\ ek = _ek /\ mk = _mk /\ c = behead _c) /\
  size c - i0 < z
```

Now I need to handle the `PRPc.PseudoRP.fi(ek, ci)` call. I need a spec that tells us `pi = AESi ek ci`.

In phoare mode, the call spec needs to capture that when `fi` is invoked with arguments `(ek, ci)`, it returns `AESi ek ci`. The challenge is formulating this correctly in EasyCrypt's call syntax, where I need to specify what the result should be in terms of the input arguments to the called procedure. I'm getting confused about the exact syntax for the `call` statement in EasyCrypt's hoare mode. The specification should relate the precondition (what's true before the call) to the postcondition (what's true after), both referring to the calling procedure's memory. For the specific call to `fi(ek, ci)`, I need to track that `ci` comes from the witness array before the call, and then the result gets assigned to `pi`. names like `k` and `x` directly. Let me reconsider the approach — maybe I should use `ecall` to reference an existing lemma instead, or try `sp` to step through the assignment first, then handle the call differently. Actually, I'm going to try a different tactic altogether and see if I can use `conseq` or work through the proof more carefully before attempting the call.
