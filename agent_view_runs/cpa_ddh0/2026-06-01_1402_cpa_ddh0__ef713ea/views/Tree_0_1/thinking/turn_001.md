# Tree-0.1 · turn 1 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:04:17.812Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv => //.`

---

Let me analyze the proof goal and plan my approach.

The goal is to prove:
```
Pr[CPA(ElGamal, A).main() @ &m : res] = Pr[DDH0(DDHAdv(A)).main() @ &m : res]
```

This is a probability equality between two games. I need to show that the CPA game with ElGamal is equivalent to the DDH0 game with the DDH adversary constructed from A.

Let me think about the structure:

**CPA(ElGamal, A).main():**


The CPA game generates a keypair where the public key is g^sk, has the adversary choose two messages, flips a coin to pick one, encrypts it as (g^y, g^(sk*y) * message), and checks if the adversary guesses the bit correctly.

**DDH0(DDHAdv(A)).main():**
The DDH0 game samples a DDH tuple and passes it to the adversary I'm constructing from A. I need to trace through how the adversary uses the DDH challenge to simulate the CPA game. I'm completing the ciphertext definition and then comparing the two games to show they're structurally identical—the CPA security reduces to DDH because the public key in CPA plays the same role as the generator base in DDH0.

For the formal proof, I'll start with `byequiv` to establish the pRHL equivalence between the two main procedures, then inline everything to expose the underlying structure and step through the games using tactics like `auto`, `swap`, and `rnd` to handle the random sampling and procedure calls.

The key insight is that after inlining, both sides will have similar sampling steps and calls to the adversary's choose and guess methods, and I can use the algebraic property that `(g^x)^y = g^(x*y)` to show the ciphertexts are identically distributed.

Examining the inlined programs... I need to work through the proof tactics systematically. After applying `byequiv` and `proc` to flatten both sides, I'll inline all the function calls to expose the underlying structure. Then I can match up the sampling order and group operations between the two games, using algebraic reasoning to show the expressions are equivalent. swap to align the samplings, `auto` / `wp` / `rnd` / `call` to match the steps, and `smt` for the algebraic equivalence. The standard EasyCrypt approach would use `byequiv`, inline everything, swap to reorder the random sampling on the right-hand side, then apply `wp`, `rnd`, and `call` tactics before finishing with algebraic simplification.

Let me reconsider the structure more carefully by looking at what the inlined code actually produces. After expanding the key generation and encryption procedures into the main CPA game, I get the sampling of the secret key, the public key computation, the adversary's choice phase, the random bit selection, and then the encryption of the chosen message with a fresh random value.

Now I'm noticing a mismatch in how the adversary interface is defined—the `A.guess` procedure seems to expect a single ciphertext argument that's a pair, but I need to verify whether the module type signature matches what I'm actually passing. Now I'm comparing the two game executions side by side. The left side samples the random exponent after the adversary's choices, while the right side samples it upfront before calling choose. This changes how the group elements are constructed—one uses the secret key exponentiated by a fresh random value, the other uses a fixed exponent multiplied with a sampled value. These are the critical structural differences that will determine whether the games are equivalent.

For the proof strategy, I need to use statement swapping to reorder the sampling in the left game so it aligns with the right game's structure. The key insight is that the random sampling of the exponent is independent of the adversary's output, so it should be movable past the procedure call without violating any data dependencies. I can't swap past procedure calls in EasyCrypt's pRHL, so I need a different tactic. Let me try working backwards from the return statement using `wp`, then handle the random samplings and procedure calls in sequence—starting with A.guess, then the random bit, then A.choose, and finally the initial key sampling.

Now I'm laying out both sides after inlining to see how to align them properly. The left side samples sk first, then has A.choose, then samples b and y, then calls A.guess. The right side samples x and y0 upfront, then calls A.choose with x, then samples b, then calls A.guess with y0. I need to figure out how to reorder these to match up—particularly getting y into the right position on the left side and aligning the key material between sk and x. - Match b with b
- Match the A.guess calls

One approach: swap in RHS to move y0 after A.choose:

After swap:
RHS:
1. x <$ dt;
2. (m0, m1) <@ A.choose(g^x);
3. y0 <$ dt;
4. b <$ {0,1};
5. b' <@ A.guess(g^y0, g^(x*y0) * (b?m1:m0));
6. return b' = b;

Now LHS and RHS are more aligned but we still have the order of b and y swapped:
LHS: A.choose, b, y, A.guess
RHS: A.choose, y0, b, A.guess

I need to swap b and y0 to align them. The question is whether I can use swap past procedure calls in EasyCrypt pRHL—I think it works as long as there's no data dependency. Actually, this looks like a standard EasyCrypt example, so the typical approach would be to use byequiv with inline and then carefully swap statements to match the procedure calls.

Writing EasyCrypt proof... I need to establish those equalities before the call, then work backwards through the sampling statements. The issue is that after inlining, the samplings appear in different orders on each side—on the left I have `y` then `b`, but on the right `b` comes before `y0`. I need to figure out how to match them up with the `rnd` tactic when they're not in the same positions.

Let me reconsider this using a swap approach. After inlining, I have the full code on both sides: the left generates `sk0`, calls `A.choose`, samples `b`, then `y0`, and finally calls `A.guess`. The right side generates `x`, then `y`, calls `A.choose`, samples `b0`, and calls `A.guess`. To align these properly, I need to decide whether to swap statements on one side or the other to get the samplings in matching order.

If I move the `y` sampling past the `A.choose` call on the right (assuming EasyCrypt allows swaps through calls when there are no dependencies), I can get both sides to have the same sequence: sample, `A.choose`, sample, sample, `A.guess`. But then the order of the second and third samples differs between left and right—left has `b` then `y`, while right has `y` then `b`—so I'd need another swap to fix that.

I'm trying to figure out the exact syntax for EasyCrypt's swap tactic: whether it's `swap{side} pos count` to move a statement forward or backward, or something else entirely.

Let me look at how the standard proof for this lemma actually works. The typical approach uses a series of tactics to inline everything and then strategically reorder statements to align the two sides of the equivalence, followed by automation to handle the remaining goals.

Actually, I think the cleaner approach is to bring the relevant variable into the right position on one side, then let automation handle the rest. But I need to be more careful about which tactics work in the relational setting—`auto` might not be sufficient for procedure calls, so I should think through the pRHL tactics more systematically. The key ones are weakest precondition for deterministic code, random sampling for distributions, procedure calls with preconditions, statement reordering, and simulation tactics.

Let me just start with `byequiv` as the entry point since that's the natural way to show probability equivalence between these two games, rather than trying to build it up with `have` statements.

Now let me submit the first tactic: `byequiv => //.` to start the relational proof.
