# Tree-0.1 · turn 3 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:34:49.410Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline BR93(LRO).keygen BR93(LRO).enc.`

---

The view is truncated. Let me read the full workspace view to see the complete goal.

Now I can see the full pRHL goal:

```
LHS:                                     RHS:
Log(LRO).init()                 (1)      Log(LRO).init()               
(pk, sk) <@ BR93(LRO).keygen()  (2)      (pk, sk) <$ dkeys             
(m0, m1) <@ A(Log(LRO)).a1(pk)  (3)      (m0, m1) <@ A(Log(LRO)).a1(pk)
b <$ {0,1}                      (4)      b <$ {0,1}                    


```

On the left side, we're encrypting the chosen message based on the bit b, while the right side generates a random ciphertext and plaintext instead. Then both sides run the adversary's second phase to get its guess b', and the game succeeds if the adversary correctly identifies which message was encrypted.

Looking at the postcondition, the adversary wins if either its guess matches in both games, or if the random value from Game1 appears in the adversary's query log. My proof strategy is to work backwards through the games using pRHL reasoning, starting with the return statement and working up through the adversary interactions.

The critical step is handling the `a2` call, where I need to establish an invariant that captures the "upto bad" oracle reasoning—specifically, that the encryption is indistinguishable unless the adversary queries a value that was sampled during the game. Now I'm analyzing what happens when the oracle is called on different inputs. For queries where `x` isn't the special value, both sides of the maps agree and return the same result. But when `x` equals that special value, the maps might differ—one side could have it set from encryption while the other doesn't—which would expose different results, though this triggers the bad event since the query gets logged. So the oracle invariant needs to capture that either the bad event has fired or the log queries match and the maps are equivalent except at that critical point.

I need to figure out the right EasyCrypt syntax for expressing "maps equal except at a predicate." The standard library should have something like `eq_except` that captures this relationship, likely from the `FMap` module that's already imported. Rather than guess at the exact formulation, I should verify what's actually available in the ROM theory being used. I can use `seq` or `call` to handle the shared code structure. Let me try inlining the keygen and encryption procedures on the left-hand side to make the programs more structurally similar, then use `seq` to align them properly before handling the adversary calls with the right invariants.

Writing proof tactics... I'm considering whether to inline the lazy random oracle procedure during the encryption step. When I expand `LRO.o(r)` directly, it becomes a conditional check that samples from the plaintext distribution if `r` hasn't been queried before, then retrieves the stored value — but this makes the code more complex than the direct comparison.

Let me step back and think about the overall proof strategy. For this kind of "up-to-bad" lemma in EasyCrypt, I'd typically use tactics like `seq` to split at the bad event detection point, or leverage `rnd` to couple the random samplings when the lazy oracle samples fresh values. I should start by inlining the keygen and encryption procedures to see how the proof structure unfolds.

Now I'm deciding whether to inline the oracle call as well. If I inline the encryption, I get a direct call to the oracle on the left side, and I'd need to either inline the oracle itself to reason about its conditional logic, or use a `call` tactic with an appropriate specification. The `call` approach would require setting up a complex invariant relating the global state and the random value, which seems unwieldy. So I'll just inline everything to keep the reasoning straightforward, though I need to be careful since the oracle is also called elsewhere in the code. I'm trying to figure out the right EasyCrypt syntax for selectively inlining procedures. The `inline` tactic can target specific procedures or use positional markers like `inline{1}` for the left side only, and I think I can inline both `BR93(LRO).keygen` and `BR93(LRO).enc` together since they only appear on the left-hand side anyway. Let me reconsider the code structure to see if there's a simpler approach.

Looking at the alignment between the two games, I can see the key differences: the left side calls `BR93(LRO).keygen` and `BR93(LRO).enc`, while the right side uses direct sampling and constructs the ciphertext differently. I should start by using `seq 5` to split the proof at the point where the ciphertext is computed.

Actually, let me reconsider — I need to identify where the games actually diverge. The first four steps are identical: initialization, key generation, the first adversary call, and bit sampling. The encryption step is where things split. So I should use `seq 4` to establish that after these four common steps, the state is synchronized, then handle the encryption divergence separately.

But there's a subtlety with step two: on the left side it's calling `keygen` while on the right it's directly sampling the key pair. These should be equivalent since `keygen` just does that sampling, but I need to make that equivalence explicit. Let me try inlining the keygen procedure first so both sides look identical at that point.

After inlining, I'd have the key pair destructured into `pk` and `sk`, then the adversary gets the public key and returns two messages. I sample a random bit and random value for the encryption, then call the oracle to get the ciphertext components.

Actually, I'm realizing there's a deeper issue: if I inline `LRO.o` to expose what's happening in the encryption step, it would inline everywhere it appears, including inside the adversary's oracle calls, which would blow up the proof complexity. I need to think about whether there's a way to couple these without fully inlining the oracle.

One approach is to use a one-sided call specification for the `LRO.o` step in encryption—something that says when the input hasn't been queried before, the output is uniformly distributed. But that requires careful handling in EasyCrypt's proof framework.

Actually, I realize the core issue: after inlining the encryption on the left side, the left and right games diverge in their oracle state. The left side updates `LRO.m` with the fresh random value, while the right side doesn't. So when the adversary makes its second call, the oracle memories are out of sync.

I need to formalize an "up-to-bad" invariant for the second adversary call that captures when the states can differ: either the adversary has queried the specific random value we generated during encryption, or the oracle memories agree on everything the adversary actually queries. Writing out the invariant with a disjunction that says either the bad event occurred or the relevant parts of the oracle state match...

Now checking that this invariant holds through oracle calls: if the adversary queries something other than the critical random value, both sides have identical mappings at that point so they return the same result and update identically. If the adversary queries the critical value itself, then that value is now in the query log on the right side, triggering the bad event. The invariant is maintained either way.

For the actual adversary call, I need to verify the pre and postconditions align: starting from the invariant plus equality on the adversary's input, I can show the oracle preserves the invariant structure, and combining this with the equality of outputs gives me the final disjunction I need.

Now I'm checking EasyCrypt's map library to confirm the exact syntax for the `eq_except` predicate and how to properly structure the oracle call with the right invariant... I need to clarify what the `call` tactic actually does in EasyCrypt—it's not just about the module state invariant, but about establishing that the adversary's oracle calls preserve a given invariant across both game instances. The invariant I'm setting up will generate proof obligations for each oracle procedure to show it maintains the invariant, and then the adversary's behavior follows from that guarantee. the hood) the adversary's losslessness/preservation

Hmm, but I also need to ensure that `={glob A}` and `={res}` (or the disjunction with bad) follow from the invariant.

Actually, let me re-examine. In EasyCrypt, `call (_: Inv)` for `A(O).f(args) ~ A(O).f(args)`:
- The adversary `A` is abstract
- `_` is the postcondition for the call (underscore means EasyCrypt infers it)
- `Inv` is the oracle invariant

The `call` generates goals to show that:
- Each oracle procedure `O.p ~ O.p : Inv /\ ={args} ==> Inv /\ ={res}` (preserves invariant and returns same results when inputs are equal)
- With this, the adversary call preserves the invariant and returns same results

But in the "upto bad" case, the oracle doesn't always return identical results—when the adversary queries `r`, the responses diverge. So I can't use a standard invariant that guarantees `={res}` for all queries. I need something more sophisticated that accounts for when the bad event occurs.

The disjunctive invariant I'm considering should handle this: either the bad event has already happened in one execution, or the query logs are identical and the oracle's internal state matches except for the specific predicate. When the oracle is called, if the bad condition already holds, it stays true, and if it doesn't, the invariant on the matching state ensures consistent behavior.

The key insight is that the postcondition for the adversary call should be `={res} \/ bad`—when bad occurs, we don't need result equality. So the oracle invariant needs to be compatible with this disjunctive postcondition rather than forcing `={res}` unconditionally. I'm trying to work out the exact EasyCrypt syntax for the "call upto bad" tactic, which should generate oracle goals that handle both the good case (when the invariant holds and bad hasn't occurred) and the bad transition case. Since both sides use the same `Log(LRO)` module, I can try a simpler approach by just focusing on how the `LRO.m` state differs between the two games. For the a2 call, I need to use an invariant that keeps the query logs synchronized and relates the game states, but the tricky part is that the `call` tactic requires the oracle invariant to imply `={res}` for each call—otherwise the adversary's behavior diverges and I can't couple the outputs. The "upto bad" approach handles this by returning identical results when bad hasn't occurred (keeping behavior coupled) and then not caring about coupling once bad happens. I'm trying to recall the exact EasyCrypt syntax for this—it might be something like `call (_: bad{2}, Inv)` or a variant with the bad event specified separately. Let me try a different angle instead: what if I inline the LRO.o call directly into the encryption step on the left side and reason about the conditional more explicitly? When `r` is outside the domain of `LRO.m`, both sides sample from the same distribution—the LHS generates a fresh value and stores it, while the RHS just samples directly—so I can couple them together. The key difference is that after this point, the LHS has `r` recorded in its map while the RHS doesn't, which matters for the case when `r` is already in the domain.

When `r` is in the domain, it means `a1` already queried it, so it's in the log. The LHS retrieves the stored value deterministically while the RHS samples fresh randomness, creating a distribution mismatch, but since the bad event has already triggered, I don't need to maintain the coupling. For the subsequent `a2` call, if we're in the first case where the maps diverged at `r`, I need to rely on the disjunctive invariant to handle the difference; otherwise the bad event already covers it.

I'm reconsidering whether inlining the encryption and LRO operations is workable, though the `a2` call still requires reasoning about the "upto bad" invariant. Let me explore using EasyCrypt's conditional tactics like `rcondf` or `rcondt` with a case split instead. The cleanest strategy seems to be inlining keygen and encryption on the left, using `seq` to isolate the common initialization from where things diverge, then handling the conditional and `a2` call with the appropriate invariant reasoning.

Now I'm thinking about whether I can sidestep the complex oracle invariant altogether by using `eager` or `lazy` to establish the "upto bad" property for the entire game transformation. Looking at EasyCrypt's actual call syntax, I need to understand what forms are available—whether it's just `call (_: Inv)` for standard invariants or if there's support for explicit pre/postconditions like `call (_: P ==> Q)`.

I'm wondering if EasyCrypt has a direct `upto` tactic or lemma that handles game-hopping with bad events more elegantly than my current approach with `byequiv`. Maybe I should reconsider the whole strategy and look at whether the fundamental lemma of game playing—something like `Pr_mu_sub` or `Pr_dist`—could give me a simpler decomposition of the probability bound.

The key insight is that I can split the advantage into two parts: showing the games are equivalent when the bad event doesn't occur, and bounding the probability of the bad event itself. This gives me the advantage bound I need.

But I'm realizing there's a subtlety with how `bad'` is defined in G0—it references `Game1.r`, which is a global variable in the Game1 module, so I need to verify that G0 can actually access it in its postcondition.

The key insight is that the "upto bad" strategy with `byequiv` requires showing `res{1} = res{2} \/ bad{2}`, where the results match when the bad event doesn't occur. Now I need to figure out how to structure the `call` for `a2` using a disjunctive invariant that captures this relationship.

Setting up the call with disjunctive invariant... I need to reconsider how the disjunctive invariant interacts with the oracle calls—the standard `call` tactic requires the oracle to return identical results on both sides, but my invariant allows the adversary's query results to differ, which breaks that assumption. I think I need to explore a different proof technique, maybe using eager evaluation or lazy sampling, to handle this mismatch between what the invariant permits and what the `call` tactic demands. Case 1: `(Game1.r \in Log.qs){2}` holds before.
- After the oracle call, `Game1.r` is still in `Log.qs{2}` (log only grows).
- So `Inv` still holds.
- But `={res}`? Not necessarily. The oracle results might differ (since `LRO.m` states could be completely different at this point).
- `call` requires `={res}`, so this doesn't work!

The issue is that once the bad event happens, the oracle results can diverge, and we can't couple them anymore. The adversary's behavior then diverges completely.

In EasyCrypt, this is handled by the "upto bad" `call` variant. I'm trying to recall the exact syntax for this kind of reasoning with abstract adversaries.

Let me step back and try a different approach. Instead of trying to prove equivalence directly, I could use `have` to decompose the probability bound into separate parts. I'm looking at the actual pRHL proof structure now. On the left side, I'm using the BR93 encryption scheme with the random oracle, while on the right side I'm sampling the ciphertext components directly from their distributions and constructing the ciphertext manually. The key difference is that the right side bypasses the actual encryption function and builds the ciphertext from random values, which is what I need to show is equivalent under the random oracle abstraction.

Now I need to work backwards from the return statement—both sides return `b' = b`, so I can use the weakest precondition tactic to handle that. Then I'll need to reason about the `a2` call, the encryption step where the divergence happens, and finally the common prefix with key generation and the adversary's first phase.

For the `a2` call, I should set up an "upto bad" invariant that tracks when the game goes wrong. Let me structure the proof by calling `a2` first with that invariant...

Writing proof tactics... I'm realizing that the standard `call` tactic doesn't quite capture the "upto bad" reasoning I need here—specifically, that if `Game1.r` isn't in the log at the end, it was never queried throughout, which means the oracle states remain identical and the adversary behaves the same way. I'd need to track this with a ghost variable or flag to formalize the reasoning properly in EasyCrypt.

Actually, I think EasyCrypt does have support for this through a specific `call` syntax that handles the "upto bad" case for abstract adversaries. The idea is to provide both an invariant for the good case and a bad event specification...

Writing EasyCrypt tactic syntax... I should inline the keygen and encryption procedures to make the left-hand side structure clearer before attempting the call, since I'm already inside the procedure body.
