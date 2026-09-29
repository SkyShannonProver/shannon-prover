# Tree-0.1 · turn 19 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:42:44.248Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witness _c) (take i c) /\ s = last (head witness _c) (take i c) /\ p = None /\ ek = _ek /\ mk = _mk /\ c = behead _c) (size c - i).`

---

The `while` invariant was accepted. The first subgoal is the loop body preservation:
```
forall z,
phoare[ body : (INV /\ guard) /\ size c - i = z ==> INV /\ size c - i < z ] = 1%r
```

This is the key subgoal: showing that each loop iteration preserves the invariant and decreases the variant. The body is:
```
ci <- nth witness c i
pi <@ PRPc.PseudoRP.fi(ek, ci)
padded <- padded ++ [s - pi]
```

Now I need to verify that after updating `s` and incrementing `i`, the invariant still holds and the variant strictly decreases. The variant clearly shrinks since `i` increases by one. For the invariant, I'm checking that the bounds on `i` remain satisfied and that the `padded` array correctly represents the decrypted values up to the new index.

The key step is showing that appending the newly decrypted block to `padded` matches what `cbc_dec` produces over the extended range, which relies on properties of how `cbc_dec` handles list concatenation and how `take` behaves with one additional element. I also need to verify that the new state variable `s'` equals the ciphertext block at position `i`, which follows from how `last` extracts the final element of the extended prefix. I need to verify that the recursive structure of `cbc_dec` applied to `rcons` matches what I'm building up in the `padded` list. The key is showing that when I apply the decryption function to the extended ciphertext, the result decomposes correctly into the previous decrypted blocks plus the new block computed from the current ciphertext element and the last IV value. `head witness _c`. ✓
- If `i > 0`: `s = nth witness (take i c) (i - 1)`, and the conditional evaluates to `nth witness (take i c) (i - 1)`. ✓

So the equality `last (head witness _c) (take i c) = if 0 < i then nth witness (take i c) (i - 1) else head witness _c` follows directly from how `last` is defined on lists.

This proof is becoming intricate, and using the `wp; call; auto; smt(...)` tactic would require me to feed the SMT solver several key lemmas: the recursive definition of `cbc_dec_rcons`, properties of list operations like `take`, `rcons`, `last`, and `nth`, the size relationships, and the ring axiom that subtraction equals XOR.

I'm working through the tactic sequence now—`wp` to discharge the assignments, then `call` to handle the pseudorandom function invocation, followed by `wp` again to absorb the witness assignment, `skip` to convert to a logical goal, and finally `smt` with the necessary hints to close it out.

But I'm realizing the issue: using `call (_: true)` loses the crucial relationship between `pi` and the actual output `AESi ek ci`. The call spec needs to be stronger—either I specify that `pi = AESi ek ci` in the call itself, or I inline the procedure body to preserve that equality. Let me think about what the procedure actually returns and how to capture that constraint properly. The `PseudoRP` module should have a procedure `fi` that takes a key and input and returns the result of applying `AESi`. Since this is a concrete procedure with no state, `inline` should work to unfold it, though it was rejected earlier at the top level. Now that I'm working within the while body subgoal as a phoare judgment, let me try inlining again to see if it succeeds in this context.

The call to `PRPc.PseudoRP.fi(ek, ci)` is one of the statements in the loop body, so I need to commit the while tactic first before tackling the body subgoal.
