# Tree-0.1 · turn 10 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:38:51.582Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (0 <= i /\ i <= size c /\ padded = cbc_dec AESi ek (head witness _c) (take i c) /\ s = last (head witness _c) (take i c) /\ p = None /\ ek = _ek /\ mk = _mk /\ c = behead _c) (size c - i).`

---

Now I have the while loop at the head with the precondition having the initial values pushed in. The program is:

```
while (i < size c) {
  ci <- nth witness c i
  pi <@ PRPc.PseudoRP.fi(ek, ci)
  padded <- padded ++ [s - pi]
  s <- ci
  i <- i + 1
}
pt <- unpad padded
if (pt <> None) {
  (p', t) <- oget pt
  b <@ MAC.verify(mk, p', t)
  p <- if b then Some p' else None
}
```

From the precondition, I can extract that `key = (_ek, _mk)` and work through the tuple structure to understand what values are bound at the start of execution.

Now I'm moving to the while loop and need to establish an invariant that relates `padded` to the `cbc_dec` function. The while tactic in phoare mode requires both an invariant and a variant, so I'm setting up the bounds on `i` and how it relates to the decryption process. 't started yet) and after each iteration. At the start with `i = 0` and `padded = []`, the decryption of zero blocks gives an empty result, and the witness at position 0 matches the initial state. After one iteration, I'm computing the ciphertext block at position 0, XORing it with the encrypted result, and verifying that the accumulated padded output matches what the CBC decryption function would produce for that single block.

The invariant I'm establishing is that at each step, the loop counter `i` stays within bounds, the encryption key and ciphertext remain unchanged, and the padded result equals what CBC decryption would give for the first `i` blocks.

Now I need to think about what variables the invariant can actually reference—in this proof mode, it can only use program variables and the logical free variables like `_ek` and `_c`. The variant that measures progress is `size c - i`.

Once I apply the loop tactic, I'll get subgoals for preserving the invariant in the loop body, establishing it initially, and showing the postcondition holds when the loop exits.

For handling the function calls inside the loop and after it, I'll need to decide whether to use `call`, `inline`, or `ecall`. Let me refine the invariant—I can actually drop `ek = _ek` since `ek` never changes, so the invariant just needs to track the loop counter, the decrypted data so far, and the current state. ci)` should return `AESi ek ci`. The body of the PRP inverse is probably just returning `AESi k x` or something similar.

Let me try formulating the invariant and see if the while tactic accepts it. Since `ek` doesn't change in the loop—only `ci`, `pi`, `padded`, `s`, and `i` change—I can reference `ek` directly in the invariant. I'm setting up an invariant that tracks the loop counter, the decrypted padding so far, and the current state variable.

Now I need to figure out how to relate the loop variables back to the postcondition. After the loop exits when `i = size c`, I'll have `padded = cbc_dec AESi ek (head witness _c) c`, and I need to connect `ek` to `_ek` and `c` to `behead _c` to satisfy the final requirement that `p = mee_dec AESi hmac_sha256 _ek _mk (head witness _c) (behead _c)`.

Since `ek`, `mk`, and `c` aren't modified by the loop, they should be preserved if they start with the right values, but in EasyCrypt's Hoare logic I need to explicitly state what's being maintained in the invariant rather than relying on an implicit frame condition.

The while tactic will generate obligations for loop body preservation, initialization, and the post-loop state. After the loop exits, the remaining code unpads the ciphertext, extracts the plaintext and tag if successful, and then verifies the MAC before returning the result.

For the invariant to work through to the final postcondition, I need to track that `padded` equals the CBC decryption of the ciphertext up to the current iteration, maintain the key values `mk` and `ek`, keep `p` as `None` initially, and preserve the state variable `s` at each step. Let me formalize this as an invariant that captures the decryption progress and carries the necessary values through to the post-loop verification.

The variant is simply the remaining ciphertext length. Now I'm checking whether this invariant actually holds—there's a subtle point about how `head witness _c :: c` behaves when `_c` is empty, and how the indexing into this reconstructed list aligns with the loop counter. After the loop terminates with `i = size c`, the invariant should give me exactly what I need for the MAC verification step. I'm working through whether EasyCrypt's SMT solver can automatically recognize that subtraction in the boolean ring is equivalent to XOR. Then I need to verify the loop invariant more carefully—after each iteration, the padded value should equal the CBC decryption of the ciphertext up to that point, using `rcons` to extend the accumulated plaintext blocks. The cases check out: when `i = 0`, the witness value matches the base case, and when `i > 0`, it aligns with the previous element in the ciphertext. The invariant holds, though it requires careful reasoning about `nth` and `take` operations that might be beyond what automation can handle directly. Let me explore whether a fold-based formulation of `cbc_dec` would simplify things. result of the fold after processing all ciphertext blocks, which should equal the original CBC decryption result. The proof then verifies that the final padded output matches what we'd get from the direct decryption function, confirming the equivalence between the fold-based and direct implementations. Verifying the fold operation... The key properties I need are commutativity of XOR, the definition of `rcons` as list concatenation, and a standard fold lemma about how folds distribute over cons operations. This might be enough for the automated solver, though I could also try a simpler approach using the fold accumulator more directly.

Instead of referencing `cbc_dec_block` or `foldl` explicitly, I could capture the relationship inductively through the invariant itself—tracking the pair `(s, padded)` with conditions on the loop index and the relationship between the current state and the ciphertext. The tricky part is handling the conditional logic for what `s` should be at each step without making the invariant too complex.

I'm exploring whether using `nth witness` on the extended list `(head witness _c :: c)` would give me a cleaner formulation, though EasyCrypt might not automatically simplify the indexing. Another approach is to split the invariant into separate implications for the base case and inductive case, or track the last state more explicitly as part of the invariant structure. I'm reconsidering the approach—maybe I should try a simpler while loop invariant that just bounds `i` and lets the post-loop verification handle the functional correctness, but that won't work since I need to connect `padded` to the spec. Let me try stating a full invariant that tracks the bounds on `i`, preserves the key variables, and maintains that `padded` equals the CBC decryption of the first `i` ciphertext blocks, with `s` as the last plaintext block seen so far.

Actually, there might be a cleaner path: I could use `conseq` to unfold `mee_dec` in the postcondition first, then match the program against that unfolded definition. Or I could try `ecall` for the MAC verification call, since that works backwards in phoare mode. Let me check what the `mee_encrypt_correct` lemma above this one looks like—it's also a phoare lemma about MEE procedures, so its structure might hint at the intended proof strategy. So the loop iterations are building up the padded list correctly—each step matches what `cbc_dec` produces. Now I need to work through the phoare while tactic to verify the invariant holds and understand what obligations it generates.

I'm a bit uncertain about whether the while tactic will handle code after the loop properly, or if I need to use `seq` first to separate them. Let me just attempt it and see what happens. I'll start with a simplified invariant that tracks the loop counter, the accumulated decrypted values, and the current state.

Writing simplified invariant... I need to figure out whether `mk` should stay in the invariant since it's not used in the loop body itself, only in the MAC verification afterward. In EasyCrypt's Hoare logic, variables aren't automatically preserved across loops unless they're explicitly mentioned in the invariant, so I'd need to include `mk = _mk` if I want to use it after the loop terminates. Let me think through what the `while (INV) (VAR)` tactic actually generates in terms of subgoals.

Writing the invariant... The program uses subtraction in the ring, which should reduce to XOR since the ring instance defines subtraction as addition with the opposite element, and the opposite is the identity function. I need to verify that EasyCrypt will recognize `s - pi` as equivalent to `s +^ pi` when checking against the functional specification. Writing the while invariant... I'm checking how `witness` works in EasyCrypt—it's a default value of type `block` that gets used when accessing the head of a list. The `last` function should correctly return either the last element of a taken slice or the default if the slice is empty, which handles both the base case and subsequent iterations properly. Let me test this approach. I'm wondering if the `take` function could create complications here. In EasyCrypt, `take` extracts the first `n` elements from a list, so I need to verify that `take (i + 1) c` equals the previous elements plus the current one—something like `rcons (take i c) (nth witness c i)` when the index is in bounds. There should be a lemma in the list library for this relationship. For the `cbc_dec` relation, I also need to show how decryption distributes over this construction, building up the result by appending each newly decrypted block. Verifying the case analysis for the conditional: when `i = 0`, the result should be `iv`, and when `i > 0`, it should be the previous element in the ciphertext sequence, which matches the invariant that tracks the last decrypted block. The key difference is that `last` uses its first argument as the default for empty lists, while `nth` uses `witness`. For empty lists, `last iv []` returns `iv`, and the conditional also evaluates to `iv`, so they match. For nonempty lists, both expressions return the last element. I need to verify the behavior with negative indices—in EasyCrypt, `nth witness xs n` returns `witness` when `n < 0`, so `nth witness [] (-1) = witness`.

Now I'm working through the specific case where `size (take i c) = i` (since `0 <= i <= size c`), which means the conditional in the `cbc_dec_rcons` lemma simplifies to checking whether `0 < i`, and both formulations should align on what value gets returned.

The challenge is whether EasyCrypt's automation can handle this chain of reasoning. I'd need to provide hints about `cbc_dec_rcons`, the properties of `take` with respect to size, and facts about `rcons` concatenation, plus some ring algebra for the XOR operations. But maybe there's a cleaner path using `conseq` to rewrite the postcondition by unfolding `mee_dec` and `cbc_dec` into their fold-based definitions first.

Let me just try running the while tactic with my invariant to see what subgoals actually emerge. If they're tractable, I can work with them; otherwise I'll refine the approach. The main thing I'm uncertain about is whether `cbc_dec` unfolds properly inside the invariant since it's a recursive function with pattern matching, but that should be fine in EasyCrypt.

One thing I need to verify though: in phoare mode, when I use `while (INV) (VAR)`, does it expect the while loop to be the only remaining statement, or can there be code after it? Looking at what's left after `sp.`, I have the while loop followed by unpadding and a MAC verification check. The while tactic should handle the loop and leave the subsequent statements as a separate subgoal, but let me just try it and adjust if needed.
