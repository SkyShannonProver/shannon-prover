# Tree-0.1 · turn 19 · undo_to_checkpoint

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:52:55.024Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_1_e7af3196b620a0de"}`

---

Good progress. Now I'm back to 2 goals. Let me see the full view to understand the current goal.

Now I can see the full goal. The `call (_: true, bad)` was processed successfully. The current goal is:

```
LHS:
(1)  Log(LRO).init()
(2)  kp <$ dkeys
(3)  (pk, sk) <- kp
(4)  (m0, m1) <@ A(Log(LRO)).a1(pk)
(5)  b <$ {0,1}
(6)  pk0 <- pk
(7)  m <- if b then m0 else m1


(8)  r <$ drand
(9)  h <@ LRO.o(r)
(10) c <- (f pk0 r, h +^ m)

RHS:
(1)  Log(LRO).init()
(2)  (pk, sk) <$ dkeys
(3)  (m0, m1) <@ A(Log(LRO)).a1(pk)
(4)  b <$ {0,1}
(5)  Game1.r <$ drand
(6)  h <$ dptxt
(7)  c <-
```

On the left side, I'm sampling a random value, applying the LRO oracle to it, and then constructing the challenge pair. On the right side, the process diverges—instead of using the oracle, it's sampling from the plaintext distribution directly.

Now looking at the postcondition, it's asserting that for any possible outcomes and random queries, either the adversary's results match across both games, or the random value from the right game appears in the query list. This captures the core security property: the games are indistinguishable unless the adversary somehow queries the specific random value that was used. {1} = true`, `b{2} = true`, `qs_R = []`, the postcondition becomes `true = false \/ false`, which is false — so this postcondition is unsatisfiable.

The problem is that with `call (_: true, bad)` and a `true` invariant, the postcondition must hold for ALL possible return values, but the invariant is too weak to constrain them meaningfully. The call gives us no information about what the return values actually are, making it impossible for the postcondition to be satisfied universally.

Actually, rereading the postcondition more carefully — it's quantified over all `result_L`, `result_R`, and `qs_R`, which means it's claiming something that's clearly false in general. Unless this is actually the precondition for the remaining code after the call, not a postcondition itself.

So the pRHL judgment is really about the code before the call establishing a state where, for any possible return values and any possible log entries afterward, the overall postcondition would hold. The postcondition isn't asserting something about specific values, but rather constraining what the code before the call must set up.

Since the call with `true` as the invariant provides no information about the return values or the log, the postcondition needs to be satisfiable for all possible combinations. But testing a concrete case—where `result_L = true`, `result_R = false`, and both `b{1}` and `b{2}` are `true`—shows the postcondition evaluates to false. This means the postcondition is unsatisfiable, confirming that this call generates an unprovable goal.

The real issue is that `true` doesn't establish any relationship between the oracle states on the two sides. A proper invariant like `eq_except` or a forall quantifier would couple them correctly, but EasyCrypt rejected those. So I'm caught between an invariant that's too weak to prove anything and one that the tool won't accept.

Maybe the "upto bad" call tactic isn't the right tool here. I should try a different strategy—perhaps inlining the oracle directly and reasoning about the encryption step with explicit if-then-else logic instead.

Or maybe I should abandon the equivalence-based approach entirely and work directly with probability bounds using EasyCrypt's probability lemmas to bound the original game against Game1 plus the probability of the bad event. I'm working through the probability inequalities using partitioning on the `bad` event. Since `Pr[G1 : res ∨ bad]` equals `Pr[G1 : res ∧ ¬bad] + Pr[G1 : bad]` by splitting on whether `bad` occurs, I can establish that `Pr[G0 : res] ≤ Pr[G1 : res ∨ bad]` if I can connect the two games through this decomposition.

Now I'm setting up the proof structure using a game equivalence argument that relates the result in the first game to the result or bad event in the second game, then applying transitivity with the probability union rule to finish.

But I still need to actually prove that byequiv statement, and I'm running into the same coupling issue with the adversary's second call. The postcondition here is an implication rather than an equality, which is weaker, but that doesn't actually help me couple the adversary's behavior across games.

Let me step back and try a completely different approach—maybe I should abandon the byequiv tactic altogether and instead reason directly at the probability level using hoare-style reasoning or other probability-based tactics.

I could try establishing that the probability difference between the two games equals the probability of bad events occurring, since the games behave identically when bad doesn't happen. But the challenge is that the bad flag doesn't exist in the original game, so I need to be careful about how I set up this argument. Let me think through what variables actually exist in each game and how to properly account for the divergence. Looking at the postcondition with the `true` invariant, I see it quantifies over three variables—the left and right return values plus the right-side log—but provides no constraints relating them, making the whole thing unsatisfiable. With a proper invariant like `={Log.qs, LRO.m}`, the returns would match and the logs would be equal, which would actually satisfy the postcondition.

So the real puzzle is why EasyCrypt rejected the call even with that stronger invariant—it seems like the issue might be that EasyCrypt checks whether the call's postcondition entails the overall postcondition at application time, not just whether it's satisfiable. I'm realizing the entailment checker might be struggling with the structural matching when the invariant adds extra conjuncts to the postcondition. Let me try a different tactic—using `conseq` to simplify the postcondition before the call, which should give me more control over what EasyCrypt needs to verify. the `call` can handle, that might work.

But wait, I'm currently in a state where `call (_: true, bad)` was already accepted. Let me undo that and the other completed goals, and try a different approach.

Actually, you know what, let me try to undo back to before the `call` and try using `conseq` to change the postcondition, and then use a different `call` approach.

Let me undo to before the `call (_: true, bad)` step.

Actually, wait. I'm currently at a state with the postcondition involving `forall`. Let me first undo the `call` and its sub-goals.

OK, let me think about the overall approach again.

State: after `byequiv`, `proc`, `inline BR93(LRO).keygen BR93(LRO).enc`.

Now I have a pRHL judgment where the LHS has the oracle call inlined with the key generation and encryption, while the RHS uses random sampling for the hash. The postcondition states that the adversary's bit guess matches the challenge bit on both sides, or the bad flag is set on the right. For the second adversary call, I need to apply "upto bad" reasoning, but the syntax `call (_: non_trivial_inv, bad)` isn't working. Let me try inlining the oracle on the left side instead and handling the conditional logic differently. I'm stuck on how to make the memory states align after inlining—the RHS doesn't sample `LRO.m.[r]` during encryption, so even if I add a dead sampling step, I can't modify the program itself. Let me explore other proof techniques instead: maybe I can use `seq` to split at the `a2` boundary and apply `conseq` with `byequiv`, or try `exists*` to case-split on the value of `r` and reason conditionally about each case. I'm also considering working backwards from the end with `wp` to handle the ciphertext assignment.

Actually, I realize `wp` won't help since `a2` is the final call—I need to process it first. The real question is whether I can use `conseq` to weaken the postcondition before the call, making it easier to prove the `a2` step matches.

Let me look at how the reference proof handles this. It uses `call` directly after `proc`, which suggests there might be a simpler tactic I'm missing for dealing with oracle calls in this context.

The issue is that in `eq_Game1_Game2`, both games share identical oracle state, so `call (_: ={glob Log, glob LRO})` works seamlessly. But here the oracle state diverges after the encryption step, which breaks that assumption for the second call. I need to figure out what makes the oracle calls work differently between these two proofs. Looking at the postcondition more carefully, I see it's asserting a boolean equality: either both games agree on whether `b' = b`, or the bad event occurred in Game1. This is the key insight for handling the "upto bad" reasoning in the proof.

For the `a2` call, if I can establish that either the global state of `b'` and the log agree between games, or the bad event happens, combined with the earlier equality on `b`, then the postcondition should follow. The challenge is figuring out whether to use a concrete hoare spec with the disjunction built in, or leverage EasyCrypt's "upto bad" call variant more directly.

Actually, I'm wondering if the initial error was something straightforward like a namespace issue with `eq_except`. Since the ROM clone might shadow the original definition, I should try qualifying it explicitly with `SmtMap.eq_except` to ensure I'm using the right predicate for comparing the maps except at a specific key.

Writing the qualified call... I'm realizing the real problem might be in how EasyCrypt verifies the postcondition after the call—it needs to prove that the conjunction of the call's postcondition and my invariant entails the overall postcondition, which requires reasoning about the relationship between `b'` and `b` that may not be available in the current context. b{1}` and `b{2}` are not part of the call's precondition/postcondition — they're in the ENCLOSING context.

With `inv = true`: the call postcondition is `(={b'} /\ true) \/ bad` = `={b'} \/ bad`. EasyCrypt checks this against the overall postcondition using the ENCLOSING context (which includes `={b}`). It can derive: `={b', b} => (b'{1} = b{1}) = (b'{2} = b{2})`. And the bad disjunct matches. So it's entailed.

With `inv = ={Log.qs}`: the call postcondition is `(={b'} /\ ={Log.qs}) \/ bad`. EasyCrypt tries the same check but with extra conjunct `={Log.qs}`. The entailment should still hold since extra conjuncts only strengthen the premise. But maybe EasyCrypt's entailment checker is being overly strict about the postcondition form not matching exactly.

Actually, I think the real issue is how the `call` tactic processes the final statement. When it consumes `b' <@ A(O).a2(c)` with no remaining code, the call establishes `(={b'} /\ inv) \/ bad`, and this needs to entail the overall postcondition which also depends on the enclosing context. Looking at how EasyCrypt processes the `call` tactic, it generates a precondition for the prefix code that establishes the necessary invariants and relationships between the two programs before the function call occurs. I'm working through the logic of the universal quantifier in the precondition—for any pair of results satisfying the invariant, the postcondition needs to hold. Since the results are equal and the invariant establishes that `b{1} = b{2}`, the postcondition simplifies to a tautology, so the proof should go through. the call returns). So when I use `call (_: Inv, bad)`, the postcondition needs to account for what happens to that log state, and it becomes more constrained than when using `call (_: true, bad)`.

Looking at the postcondition with the universal quantifier over all possible `qs_R` values, if I set `qs_R` to the empty list, the disjunction collapses to requiring `(result_L = b{1}) = (result_R = b{2})` hold universally. This forces `b{1} = b{2}` from the program state itself, which isn't something I can universally quantify over—it's a concrete fact about the current execution.

Even after substituting `b{1} = b{2}`, the condition becomes `result_L = result_R`, but since both results are universally quantified over all possible values, this equality can't hold for arbitrary choices. The postcondition is fundamentally unsatisfiable because the `true` invariant fails to establish any coupling between the left and right results, making this goal unprovable. Writing EasyCrypt tactics... I'm stepping back to reconsider the whole approach. The key insight is that EasyCrypt's "upto bad" mechanism works through the `: bad` annotation on `byequiv`, which automatically handles the probability decomposition. Inside the equivalence proof, I should use `call` with a proper invariant, and the annotation changes how that tactic behaves to account for the bad event. I'm realizing the syntax might need the bad event annotation placed differently—maybe the postcondition should express that when the bad event doesn't occur, the results match, and then I specify the bad event separately after the byequiv spec. Let me test whether this formulation actually parses correctly in EasyCrypt.

Actually, I should backtrack to the original probability goal using `undo_to_checkpoint` since I've accumulated a lot of committed tactics and need a clean slate to experiment with the right syntax.
