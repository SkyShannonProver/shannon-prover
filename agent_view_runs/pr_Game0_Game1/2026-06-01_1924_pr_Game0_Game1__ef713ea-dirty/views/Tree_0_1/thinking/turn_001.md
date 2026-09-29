# Tree-0.1 · turn 1 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:28:54.790Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_ : ={glob A, glob LRO} ==> ={res} \/ (Game1.r \in Log.qs){2}) => //.`

---

Let me analyze the proof goal and plan my approach.

The goal is:
```
Pr[BR93_CPA(A).main() @ &m : res] <=
Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]
```

This is a probability inequality. The lemma `pr_Game0_Game1` states that the probability of the CPA game is bounded by the probability of Game1 plus the probability of a "bad event" (the random value `r` being in the adversary's query log).


This is a classic game-hopping argument where the two games are identical except when the adversary queries the random oracle on the specific value sampled during encryption. I'll need to use an equivalence proof to show the games match until this bad event occurs, then apply the fundamental lemma of game playing to bound the difference by the probability of the bad event. the two games. Or use the `fel` (failure event lemma) tactic. Or use a direct probability argument with `have` chains.

Looking at the goal structure more carefully, this is the classic "up-to-bad" pattern where I need to show that the probability in one game is bounded by the probability in another game plus the probability of a bad event. The key insight is that `byequiv` alone won't work here since I'm dealing with an inequality involving three probability terms, not just an equivalence. Instead, I need to establish that when the bad event doesn't occur, the two games produce equivalent results, then use that to decompose the probability bound into manageable pieces. The typical EasyCrypt approach is to use `byequiv` with a postcondition showing that either the results match or the bad event happened, which lets me derive the final inequality. I need to establish that `Pr[G0 : E] <= Pr[G1 : E \/ F] <= Pr[G1 : E] + Pr[G1 : F]` by first using `byequiv` to show the games agree except when F occurs, then applying the union bound to split the probability. I can use the union bound here—since `Pr[G1 : res] + Pr[G1 : bad] >= Pr[G1 : res \/ bad]`, if I show `Pr[G0 : res] <= Pr[G1 : res \/ bad]` via `byequiv`, I'm done. The key is demonstrating that whenever G0 returns true, either G1 also returns true or the bad event occurs, which means G0 and G1 behave identically when bad doesn't happen.

Writing EasyCrypt proof... I see the issue now—the right-hand side is actually a sum of two probabilities, not a single event, so `byequiv` alone won't directly give us what we need. I should use a two-step approach: first apply `byequiv` to relate the probabilities of the `res` event between the two games, then use a probability union rule to decompose the sum on the right-hand side. I need to work through the probability reasoning more carefully. The key insight is using the `Pr[mu_or]` lemma in EasyCrypt, which states that the probability of a disjunction is bounded by the sum of individual probabilities. So I can establish that `Pr[G0 : E] <= Pr[G1 : E \/ G]` through an equivalence proof, then apply the lemma to decompose it into `Pr[G1 : E] + Pr[G1 : G]`, giving me exactly the bound I need. I can show `Pr[G0 : A] <= Pr[G1 : B \/ C]` using `byequiv` with a postcondition that links the result from the first game to the disjunction in the second game, then apply the union bound to finish the proof.

For the intermediate step, I need to use `byequiv` with the specific syntax for inequality judgments, setting up the precondition on the initial state and the postcondition to relate `res{1}` to `(res{2} \/ (Game1.r \in Log.qs){2})`. Let me work through what happens after applying `byequiv` here...

Once I apply `byequiv` for the inequality case, I'll get a single probability goal on the right-hand side, and then I need to decompose `Pr[G1 : res \/ bad]` into `Pr[G1 : res] + Pr[G1 : bad]` using the union bound. Let me try submitting the `byequiv` tactic with the seed suggestion and see what the resulting goal looks like.

Actually, I'm realizing that `byequiv` might not work directly here since the right-hand side is a sum of two probability terms rather than a single `Pr[...]` expression. I should use a `have` statement to first establish an intermediate inequality that rewrites the goal into a form where the RHS is a single probability of a disjunction, which I can then handle with the union bound inequality. I'm seeing how Game1 overrides the BR93_CPA module to inline the key generation and modify the encryption process—instead of calling the standard encryption procedure, it directly samples randomness and plaintext, then constructs the ciphertext by combining the encrypted randomness with the XORed message. The critical part is that this bypasses the normal `H` oracle call that would happen in the standard encryption.

The key insight is that these two approaches produce identical results unless the sampled randomness `r` happens to collide with something the adversary has already queried to the random oracle. This is the "bad event" that breaks the equivalence—when `r` is in the oracle's query log, the lazy sampling behavior differs between the two games. So I need to prove the games are equivalent up to this bad event using EasyCrypt's `byequiv` tactic with a postcondition that allows the games to diverge only when this collision occurs.

The standard proof strategy decomposes the probability bound into three parts: first, show the games are identical when the bad event doesn't happen, then account for the probability of the bad event in each game separately. This requires establishing that the bad event itself has the same probability in both games since it's determined by the same underlying randomness.

Looking at how EasyCrypt's `byequiv` works for inequality goals, when proving `Pr[c1 : E1] <= Pr[c2 : E2]`, the tactic needs a postcondition where the first game's event implies the second game's event. The challenge here is that the right-hand side is a sum of probabilities rather than a single event, so I need to think about how to structure the equivalence to handle that form.

The "up to bad" variant of `byequiv` might be the right approach—it lets me prove equivalence on the good path while treating a bad event as the difference between the two sides. I'm working through the exact syntax for the `byequiv` tactic in EasyCrypt to handle this probability bound, trying different formulations of the post-condition and bad event specification. Given the constraints of the proof manager, I should probably just attempt the simplest version and see what feedback I get. I'm not confident in the syntax, so let me start with `byequiv => //=.` and reconsider the approach. What I really need here is the fundamental lemma of game playing—the probability splitting lemma. In EasyCrypt, I can express this by setting up a pRHL judgment where the postcondition requires the results to match when the bad event doesn't occur, and then specifying the bad event itself. EasyCrypt will automatically derive the probability bound from the equivalence judgment and side conditions. Let me load the MCP tool schema first to try this out.

Let me read the rest of the file to see Game1's definition and understand the full structure.

Now I understand the full picture. Let me analyze the goal:

```
Pr[BR93_CPA(A).main() @ &m : res] <=
  Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]
```

This is the fundamental lemma of game playing. Game1 differs from BR93_CPA(A) in that:
1. Key generation is inlined: `(pk, sk) <$ dkeys` instead of calling `BR93(LRO).keygen()`


2. The encryption step replaces the RO call with direct sampling from the plaintext distribution

The key insight is that the lazy random oracle returns the same distribution for fresh queries, so the games are identical unless the challenge value was previously queried—in which case one game uses the cached value while the other samples fresh. This is the classic "up-to-bad" argument in EasyCrypt, where I need to bound the probability of this bad event occurring.

The standard approach decomposes the goal using the union bound: I show the games are equivalent when the bad event doesn't happen, then add the probability that the bad event occurs in Game1. Now I'm working through the right `byequiv` tactic with the "upto bad" syntax to formalize this reasoning. this specific syntax for "byequiv ... : bad" might not be correct in EasyCrypt. Let me think about what's available.

Actually, in EasyCrypt there's a lemma/tactic pattern for the fundamental lemma. The goal structure `Pr[G0 : E] <= Pr[G1 : E] + Pr[G1 : F]` can be handled by showing the probability of E in G0 without F' is at most E in G1 without F, plus the probability of F' in G0 is at most F in G1, which gives us the desired bound. But this requires defining F' in G0, which gets complicated.

Looking more carefully at EasyCrypt, there is an "up to bad" reasoning tactic with syntax like `byequiv (_ : pre ==> post) : bad` where bad is the bad event, splitting the goal into subgoals. I'm trying to figure out whether `byequiv` actually handles `<=` goals with a sum on the right-hand side, or if it only works for equality-style goals. I'm reconsidering the approach—maybe I should just try `byequiv => //=.` and see what error message comes back, since that will clarify what the tactic engine actually expects for this goal pattern. The standard EasyCrypt tactic for game-playing arguments is `byequiv`, so let me start there and iterate based on the feedback. but with a specific postcondition pattern.

For the goal `Pr[G0 : A] <= Pr[G1 : A] + Pr[G1 : B]`:

The right approach in EasyCrypt might be to first recognize this as equivalent to `Pr[G0 : A /\ !B'] <= Pr[G1 : A /\ !B]` + union bound stuff, but this gets complicated.

A simpler approach: just use `have` to split into a `byequiv` step that establishes the main probability bound, then handle the remaining union bound separately.

Actually, I think EasyCrypt's `byequiv` tactic might directly support this "upto bad" form where I specify a postcondition that says when the bad event doesn't occur, the two games produce equivalent results, and this automatically generates the right pRHL judgment with the bad event as a side condition.

Let me try the simplest version first and see if it works.

Actually, I realize the `byequiv` tactic supports an "upto bad" variant that handles exactly this pattern. The syntax takes a precondition and postcondition, where the postcondition ensures that when the bad event doesn't occur, the two games produce equivalent results. This should directly apply to our goal of bounding the probability difference by the bad event probability. I'm realizing the issue: a simple `byequiv` gives me `Pr[G1 : res \/ bad]`, but I actually need to apply the union bound to split this into `Pr[G1 : res] + Pr[G1 : bad]`, which requires composing with an additional step rather than doing it all in one tactic.

Let me try the standard EasyCrypt "upto bad" syntax with `byequiv (_: ={glob A, glob LRO} ==> !(Game1.r \in Log.qs){2} => ={res}) : (Game1.r \in Log.qs).` to see if that handles the sum form directly.

Actually, I should first look more carefully at what Game1 is doing to make sure I'm setting up the equivalence correctly. Writing the full Game1 procedure... The difference emerges when the random value has already been queried—the lazy oracle returns a cached result while the fresh game always samples new randomness. This is the classic "up to bad" scenario, and for the pRHL proof I need to establish that when the random value hasn't been queried yet, both games behave identically. The adversary's query log tracks exactly which values have been seen, so the games only diverge when that log contains the random value. Log(LRO)`, so all queries are in `Log.qs` AND in `dom(LRO.m)`
4. `b <$ {0,1}`
5. `c <@ BR93(LRO).enc(pk,b?m0:m1)` — this calls `LRO.o(r)` DIRECTLY (not through Log), so `r` is added to `dom(LRO.m)` but NOT to `Log.qs`
6. `b' <@ A(Log(LRO)).a2(c)` — more queries through `Log(LRO)`

So `Log.qs` contains ONLY the adversary's queries, not the encryption query. And `dom(LRO.m)` contains both. The key insight is that when `r \notin Log.qs`, it could still be in `dom(LRO.m)` from the encryption step, so I need to be more careful about what the condition actually guarantees.

Actually, let me reconsider: when `r \notin Log.qs`, the adversary never queried `r`, so at step 5 when we call `LRO.o(r)` directly, it samples fresh from `dptxt` since `r` isn't cached yet—this matches Game1's behavior. But when `r \in Log.qs`, the adversary queried it before, so `LRO.o(r)` returns a cached value instead of a fresh sample, creating a difference. However, I'm realizing that in Game1, `Log.qs` still tracks the adversary's queries through `Log(LRO)`, and the encryption step doesn't route through the logging wrapper, so I need to think through whether this distinction actually matters for the games' equivalence. oracle at all — it just samples `h <$ dptxt` directly. But the adversary still uses `Log(LRO)` to query, so `Log.qs` grows the same way.

Except... in Game1, the encryption doesn't query `LRO.o(r)`, so `LRO.m` doesn't get the entry for `r` from encryption. This means in Game1, if the adversary queries `r` in `a2`, it will get a FRESH value (since `r` wasn't added to `LRO.m` by encryption). In BR93_CPA, the adversary's `a2` query of `r` would return `h` (the same value used in encryption).

So the games differ in two ways when `r \in Log.qs`: if `r` is queried by `a1` before encryption, one game uses a cached value while the other generates fresh, and if `r` is queried by `a2` after encryption, one game returns the same `h` from encryption while the other returns a potentially different value. The bad event is `r \in Log.qs`, which gets evaluated at the end after both phases complete. For the proof to work, I need to show that when `r` is never queried by the adversary in either phase, both games produce identical results. When `r` isn't queried by either adversary, it was never added to `LRO.m` during encryption, so sampling fresh is identical to the direct sampling in Game1. The key coupling argument is that the adversary state and log remain synchronized across both games, with `LRO.m` matching everywhere except possibly at `r`, which the adversary never touches anyway.

Let me trace through the invariant more carefully: after initialization both games have empty logs and maps, after key generation both sample the same keypair with no oracle interaction, and when the adversary runs with the oracle, the state remains synchronized since they're calling the same oracle on identical inputs.

The key difference emerges during encryption: BR93_CPA queries the random oracle through the LRO interface, which either returns a cached value or samples fresh randomness and caches it, while Game1 just samples randomness directly without any caching mechanism. I'm analyzing the case where the adversary has queried `r` before—here `h` becomes deterministic in BR93_CPA but stays random in Game1, so I can't couple them. After encryption, both games use the log state, but they differ on whether `r` is recorded; however, this only matters if the adversary queries `r` again. I'm trying to formalize an invariant that tracks which entries match between the two logs while accounting for the fresh random value in Game1, though the formal specification in EasyCrypt is getting intricate.

The cleaner approach is to use the standard `byequiv` technique with an "upto bad" postcondition that says the results agree whenever the bad event (adversary querying `r`) doesn't occur, and separately verify that the log states align on all queries the adversary actually makes. the pRHL proof, we'd need to establish an invariant like:
```
forall x, x \in Log.qs => LRO.m{1}.[x] = LRO.m{2}.[x]
```

i.e., the oracle states agree on all adversary-queried keys.

This is maintained because:
- Before encryption: `LRO.m{1} = LRO.m{2}` everywhere (including adversary queries)
- After encryption: `LRO.m{1}` has `r` mapped, `LRO.m{2}` doesn't, but `r \notin Log.qs` (at this point, only `a1`'s queries are in `Log.qs`)
- During `a2`: each adversary query goes through `Log(LRO)`. For queries `x \neq r`, both sides return the same thing. For query `x = r`, that's when the bad event occurs, and if it happens, we don't need to maintain the coupling anymore.

This is a standard "upto bad" proof structure. For EasyCrypt, I'll use the `byequiv` tactic with a `: bad` annotation, which handles probability bounds of the form `Pr[c1 : E] <= Pr[c2 : E] + Pr[c2 : F]`. The tactic takes a pRHL judgment and produces two goals: establishing the coupling between the two games, and verifying that the postcondition implies the equivalence when the bad event doesn't occur. I'm uncertain about the exact syntax EasyCrypt uses for the `byequiv` tactic with bad events, so let me try running it and see what feedback I get. I'm considering whether EasyCrypt even supports the `byequiv ... : bad` syntax, and if so, how to structure the pre and post conditions correctly for proving the probability bound with the bad event term. I'm reconsidering the available tactics—there's no `probe_tactic`, only `commit_tactic` and undo options, so I need to be deliberate about what I try. Let me start with a straightforward `byequiv` approach using the coupling argument for the RO replacement, and if it fails I can undo and adjust the postcondition or try inlining first.

Now I'm working through the probability inequality chain: `byequiv` should give me `Pr[G0 : res] <= Pr[G1 : res \/ bad]`, then I need to apply the union bound to split that into `Pr[G1 : res] + Pr[G1 : bad]`.

Actually, I think EasyCrypt's `byequiv` with the upto-bad annotation might handle this directly—it should produce the `Pr[G0:A] <= Pr[G1:A] + Pr[G1:B]` bound in one step, so I need to check the exact syntax for that.

Let me just try the straightforward `byequiv` approach and see what happens. If it works, great; if not, the error message will tell me what to adjust.
