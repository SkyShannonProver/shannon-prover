# Tree-0.0 · turn 12 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:48:00.218Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_ : ={Log.qs} /\ eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2}).`

---

The prefix subgoal is closed (reduced from 5 to 4 remaining goals). Now I'm on the suffix subgoal — the encryption + adversary part. Let me read the full view.

Now I can see the suffix goal:

Left:
```
(1) pk0 <- pk
(2) m <- if b then m0 else m1
(3) r <$ drand
(4) x <- r
(5) r0 <$ dptxt
(6) if (x \notin LRO.m) { LRO.m <- LRO.m.[x <- r0] }
(7) h <- oget LRO.m.[x]
(8) c <- (f pk0 r, h +^ m)


(9) b' <@ A(Log(LRO)).a2(c)
```

Right:
```
(1) Game1.r <$ drand
(2) h <$ dptxt
(3) c <- (f pk Game1.r, h +^ if b then m0 else m1)
(4) b' <@ A(Log(LRO)).a2(c)
```

The right side is a more direct version that inlines the conditional and uses the global game state directly instead of storing intermediate values. Both paths converge at the adversary call with the same challenge value.

Now I'm working through the "up to bad" argument. The critical distinction is that the left version queries through the logging oracle, which either retrieves a previously stored value or samples a fresh one and caches it, while the right version just samples directly. When the queried value hasn't been seen before, the left side generates and stores it, but the right side bypasses this entirely. This difference only matters when we're in the bad event where the game's random value appears in the log.

Let me verify the relationship between the logged queries and the oracle's memory. The adversary only makes oracle calls through the logging wrapper, so every query gets recorded in the log and stored in the oracle's map. This means the domain of the oracle's memory should exactly match the set of logged queries after the prefix phase completes.

Now I can split the analysis into two cases: when the random input hasn't been queried before, both game instances produce identical outputs since they both sample fresh values, so the adversary's final bit matches across both games. When the input was previously queried, we've already triggered the bad event we're tracking, so that case is handled separately.

The key insight is that the lazy RO's internal state diverges between the two games after encryption—in one game the queried value gets cached, while in the other it's sampled fresh each time—which means if the adversary queries that same input again, they'll get different responses depending on which game they're in.

To formalize this, I need to set up the call invariant so it tracks that the LRO maps stay synchronized except possibly at the critical input, and it also accounts for the bad event where that input appears in the query log. The invariant should express that either the responses remain identical across both games, or the adversary has queried the critical input and we've detected it.

Now I'm reconsidering the approach—the standard lazy/eager sampling technique in EasyCrypt might be cleaner here. The key insight is that when the critical input hasn't been queried yet, both sides sample fresh randomness and store it identically, so they produce the same output regardless of which game we're in. I'm realizing the invariant is getting unwieldy with all these domain and value conditions. Let me step back and think about what actually matters here: after encryption, the left game stores the hash in its map while the right samples fresh, but both add the queried value to the log, which triggers the bad event. The core relationship I need to capture is how the two maps diverge at that specific query point, but maybe EasyCrypt handles this more elegantly with a simpler invariant structure that doesn't enumerate every condition. I'm working through the second case where the random value is already in the map. In this scenario, the left side keeps the map unchanged since the entry already exists, while both sides produce the same ciphertext because they're using the same fresh random values and message bits. I need to think through how `r{1}` and `Game1.r{2}` get coupled together. Both are sampled from the random number generator, so the `rnd` tactic would make them equal: `r{1} = Game1.r{2}`. This affects how `h{1}` and `h{2}` relate to each other depending on whether `r` was previously stored in the LRO cache — if it wasn't, then `h{1}` comes from the initial random value while `h{2}` is freshly sampled, but if it was stored, they'd both retrieve the cached value.

For the encryption proof, my strategy is to use structural tactics for deterministic steps, couple the random values with `rnd`, then split into cases based on whether the random value exists in the cache to handle the two different behaviors.

Now I'm thinking about how to structure this in EasyCrypt—I should use `seq` to split the proof at the adversary call, handling the encryption logic first with an invariant that captures the state after encryption but before the adversary runs.

Defining the invariant...

The invariant needs to express that the public values and ciphertexts match, the random challenge matches, the query logs match, and either the bad event has already occurred or the LRO maps are equal except possibly at the challenge point. But wait, in the bad event case where `c{1} ≠ c{2}`, I can't require `c{1} = c{2}` as part of the invariant—that's a contradiction.

Let me restructure this so the invariant branches on whether the bad event has happened: if it has, we only need the basic state alignment, but if it hasn't, we need the stronger equality conditions on the ciphertexts and LRO maps. This is getting complex though, and I'm wondering if there's a simpler way to express this.

Actually, I need to think through what happens when the adversary calls the oracle. The oracle adds queries to the log and samples new LRO values as needed, so I need to verify the invariant holds after each oracle call. When the adversary queries with something other than the challenge value, both sides behave identically since the LRO maps agree everywhere except at that one point. But when querying the challenge value itself, that's where things diverge—the left side returns what was already sampled, while the right side would need to sample fresh, and that's exactly where the bad event could trigger. The bad event is monotonic since once `r` enters the query log, it stays there because the oracle only appends to it. Proving this invariant in EasyCrypt requires showing the oracle preserves it and is well-typed, which is complex but feasible. I'm considering a simpler approach using consequence rules to strengthen the postcondition, then applying weakest precondition and randomness tactics to handle the encryption.

Actually, I think case-splitting on whether `x` is already in the map might be cleaner. I can use the `if` tactic to branch on `x \notin LRO.m` in the left program — in one case the fresh sample gets stored and read back (matching the right's behavior), and in the other case the stored value is read and the bad event triggers. This way I can handle the oracle call with a simpler invariant in each branch.

Let me start by using `sp` to push through the deterministic assignments...

Actually, `sp` processes from the beginning of both programs, so it would handle the first two statements on the left (`pk0 <- pk` and the conditional assignment to `m`), but stop on the right since `Game1.r <$ drand` is random. That leaves the left having advanced past those initial statements while the right hasn't moved yet. I'm realizing that `rnd` works from the end, so it won't help me couple the drand sampling in the middle. I need a different strategy—maybe using `seq` to split at that point or `swap` to reorder the code. Let me step back and try a more systematic approach: I'll handle the a2 procedure call first using `call` with an appropriate invariant about the oracle, then work through the encryption logic afterward.

Now I'm trying to construct a call invariant that captures the key insight: either the bad event occurs (Game1.r{2} appears in the log), or the LRO state and query log are identical on both sides. But this runs into a problem—after encryption, the left side has an extra entry at position `r` in LRO.m, so a global equality assumption breaks down in the good case. I need a more refined invariant that accounts for this difference.

Let me step back and think about the overall proof strategy differently. Rather than wrestling with a complex call invariant, maybe I should use consequence to relax the postcondition first, then work backwards from there.

Looking at the postcondition more carefully, I can rewrite it in different logical forms to understand what needs to hold: either both games produce the same result, or the left game's output differs, or the bad event occurs. The key insight is that if the games maintain proper coupling, then either the adversary sees identical views in both games, or we can bound the probability through the bad event.

For the adversary's call to the second phase, if the challenge values match and the oracle responds consistently, the outputs will align. But if the oracle behaves differently because the adversary queried the relevant value, that triggers the bad event. So the oracle's module-level invariant needs to ensure that either the bad event has occurred or the oracle's internal state agrees across both games.

I'm trying to formalize this with a logical condition that captures when the oracle domains match or diverge at the critical point, but the formulation is getting unwieldy. Let me reconsider the approach—maybe I can use a reordering technique to move the sampling past the conditional, though that requires careful handling since the sampled value is actually used in the logic.

Looking at the program structure more carefully, when `x` isn't in the map, the fresh sample becomes the output, which is the exact behavior I need to match on the right side.

When `x` is already in the map, the output comes from stored state rather than a fresh sample, but that's fine because `x` must have come from an adversary query, triggering the bad event.

So my strategy is to use program equivalence tactics for deterministic steps, couple the random samples from `drand`, then split on whether `r` appears in the query log—in the good case I can couple the fresh samples directly.

Let me try a simpler tactic sequence first: `sp; wp; rnd; rnd` to see how far that gets before handling the conditional and adversary call.

Actually, I can restructure this by moving the `r0` sampling inside the conditional—that way I only sample when needed and avoid the coupling issue with the `if` statement.

Wait, but moving the sampling changes the semantics since it becomes conditional rather than unconditional. The real issue is that `r0` gets sampled before the `if` but only used inside the true branch, so the sampling is wasted in the else case. I need to think about whether `rcondf` or `rcondt` can help simplify this.

Looking at the two cases: when `x` is not in the map, `r0` gets stored and retrieved as `h`, so `h = r0` which is equivalent to sampling directly from `dptxt`. When `x` is already in the map, `r0` is sampled but never used, and we retrieve the existing value. I'm trying to verify whether the domain of the map exactly equals the set of logged queries.

After working through the initialization and oracle calls, the domain of `LRO.m` does equal `set(Log.qs)` since both get updated together by each adversary query. Now I'm connecting this to the coupling: since `x = r` and `r{1}` is coupled with `Game1.r{2}`, the condition `x ∈ LRO.m{1}` is equivalent to checking whether `Game1.r{2}` appears in `Log.qs{1}`.

By the prefix invariant, `Log.qs{1} = Log.qs{2}`, so this reduces to whether `Game1.r{2}` is in `Log.qs{2}`. This splits into two cases: the good case where `x` isn't in `LRO.m` and `h{1}` equals `r0{1}` (which couples with `h{2}`), and the bad case where `Game1.r{2}` is already in the log, making the postcondition trivial. Now I need to verify what happens during the encryption call in the good case.

After encryption, `LRO.m{1}` has an extra entry at `r` compared to `LRO.m{2}`, so the oracle behavior diverges only when querying `r` itself—otherwise the two sides behave identically. The call invariant must track that `LRO.m{1}` is `LRO.m{2}` with `Game1.r{2}` mapped to `h{1}`, while the query logs stay synchronized until `Game1.r` gets queried, at which point we'd hit the bad event. Log.qs updated identically on both sides). When `y = Game1.r{2}`, the left side finds the value in its map while the right side samples fresh, causing responses to diverge—but this triggers the transition to the "bad" case since `Game1.r{2}` is now queried, preserving the invariant monotonically. The oracle invariant holds, though formalizing this in EasyCrypt requires a different approach than I initially considered.

Let me reconsider the call invariant more carefully. The invariant `(Game1.r{2} \in Log.qs{2}) \/ ={res}` won't work because `res` refers to the oracle's return value, not the main procedure's. I need to think through how EasyCrypt's `call` tactic actually structures the proof—it generates oracle subgoals, precondition, and postcondition subgoals, and I need an invariant that's preserved by `Log(LRO).o` on both sides.

The invariant should express that either `Game1.r{2}` is already in the query log, or the two sides have identical query logs and their LRO maps agree everywhere except possibly at `Game1.r{2}`. I'm working through how to express the map agreement condition in EasyCrypt's fmap library...

Actually, I can express "maps agree except at key `r`" more directly by quantifying over all other keys: for any key `y` that isn't `Game1.r{2}`, the map values must match at that key. This avoids needing to know the exact name of the removal function.

For the domain constraint, I need a similar quantification: any key `y` other than `Game1.r{2}` should have the same membership status in both maps' domains.

Now I'm trying to formalize the call invariant more concisely—either the bad event occurred (the query is in the log), or the logs are identical and the first map equals the second map with the extra entry added back in. This captures the relationship between the two maps without getting bogged down in verbose quantifications.

The EasyCrypt `SmtMap` update syntax `m.[x <- v]` should handle this, so I can express the invariant using that notation. But I need to think through what value gets stored: in the good case, `LRO.m{1}` has `Game1.r{2}` mapped to the original response `r0{1}`, while `LRO.m{2}` doesn't have that key yet, so the invariant would say the first map equals the second map with that entry inserted.

For the oracle preservation argument, when `Log(LRO).o(y)` gets called, both sides append `y` to the query log and then call `LRO.o(y)`, which either samples a fresh response if `y` isn't already in the map or returns the stored value. The key observation is that for any `y` different from `Game1.r{2}`, the two maps agree on whether `y` is in their domain, so the oracle behaves identically on both sides.

When `y = Game1.r{2}`, the left side has this entry in its map while the right side doesn't, so they diverge here.  However, this triggers the "bad" case where `Game1.r{2}` gets added to the query log, preserving the invariant in its second disjunct. To formalize this in EasyCrypt, I need to structure the proof with a call that maintains the invariant, inline the oracle definition in the subgoal, and handle the case split.

This is going to require many steps, so let me explore whether there's a more direct approach. Maybe I can leverage EasyCrypt's built-in tactics for the "up to bad" pattern, or restructure this as an intermediate game rather than proving the pRHL judgment directly. Actually, I'm already committed to the pRHL approach from earlier, so let me stick with it.

Let me try pushing backward from the end using `wp` to handle the `a2` call and move the postcondition back, though I realize `wp` can't cross procedure calls—I'll need to use `call` first. Let me step back and figure out the most efficient way to close this.

I can use `rcondt{1}` or `rcondf{1}` to handle the conditional on the left side by showing the condition is always true or splitting into cases. In the "good" case where `r` isn't in the log, the condition `x \notin LRO.m` holds true, so the branch executes and `h` gets set to `r0`. In the "bad" case where `r` is in the log, the condition is false since the domain of `LRO.m` contains all logged queries.

But I need to handle both cases simultaneously rather than assuming one or the other. Let me try proving the postcondition by showing that after the call, either the results match and the oracle behaves identically in both games, or the adversary's query is in the log for game 2. For the first case to work, I need the ciphertexts to be identical and the oracles to respond the same way. Let me attempt this using a `call` statement with a straightforward invariant, then apply `wp` and `rnd` reasoning to the encryption step.

Writing proof code...

Actually, I realize this invariant simplifies to just saying either the adversary's query is in game 2's log or the global state matches between games. But this won't hold after encryption because the left oracle will have an extra entry in its message log, breaking the equality even in the good case. So I need a more sophisticated invariant instead.

Let me think about handling this differently.  What if I split the proof into two cases based on whether the adversary queries the problematic record? In the good case where it doesn't, I can show both sides produce identical results despite the differing log entries, since the fresh value is properly coupled. In the bad case where it does query, the postcondition holds trivially.

The challenge is that at the time of the call, I don't know yet whether the adversary will query that record, so I need an invariant that covers both possibilities. Let me formalize this with a call invariant for the oracle that captures either the bad event occurring or the equivalence of the query logs with a controlled difference in the map entries.

Defining the invariant... Writing the call invariant... would generate:
1. An oracle subgoal: show that `Log(LRO).o` preserves this invariant (and produces `={res}` or bad event)
2. A precondition subgoal: show the pre-state implies the call pre-condition
3. A postcondition subgoal: show the call post-condition implies the desired post-condition

Wait, but the `call` for an adversary like `A(Log(LRO)).a2(c)` requires the oracle invariant and will generate an obligation for the adversary's postcondition too.

Actually, in EasyCrypt, `call (_ : Inv)` for `A(O).proc(arg)` requires:
- An oracle invariant `Inv` for `O`
- The adversary `A` can only call through `O`
- The subgoals are:
  1. `Inv ==> Inv /\ ={res}` for the oracle `O.o` (the oracle preserves the invariant and produces equal results)

But that's too strict — the oracle should be allowed to produce different results when the bad event triggers. I think I need `call (_ : Inv ==> Post)` instead, which lets me specify the oracle postcondition separately from just requiring equal results. This way I can express that the oracle maintains the invariant but the results can diverge when the bad event occurs. I need to reconsider how to structure the `call` tactic here—the standard form with just `Inv` won't capture the disjunction I need, where either the results are equal or the bad event occurs. Let me explore whether EasyCrypt allows a postcondition that includes the bad event as an alternative to equality, or if I need a different approach to handle the case where oracle results diverge. The oracle produces different results when the adversary queries `r`, which breaks the equality postcondition required by the standard `call (_ : Inv)` pattern. Even if I craft an invariant that's preserved in the bad case, the oracle still can't satisfy `={res}` when it produces unequal results, so I need a more flexible form of `call` that allows the postcondition to vary based on whether the bad event occurred. I'm reconsidering whether `byequiv` with a bad event syntax even exists in this version of EasyCrypt, since my earlier attempts were rejected. Let me try a completely different approach instead of continuing down this path—maybe I should step back and handle the oracle difference more carefully within the current strategy rather than searching for a tactic that might not be available.

Actually, I just realized the `call` tactic might support providing module invariants for individual oracle methods, and there's also `ecall` for handling "up to bad" oracle calls, though I'm uncertain about the exact syntax. Let me experiment with `call` using identical oracle assumptions first to see what subgoal it generates, or alternatively try `sim` for the adversary with a relational invariant on the globals.

But I'm running into the issue that the LRO maps aren't actually equal between the two games. Maybe I should try a different approach—instead of forcing global equality, what if I provide both an invariant and a postcondition to the `call` tactic? Or perhaps I should narrow the scope and just handle the specific case where `r` isn't already in the LRO map, which would simplify the proof obligation. the encryption:
- Left: `LRO.m{1} = LRO.m_before.[r <- r0{1}]`
- Right: `LRO.m{2} = LRO.m_before`
- `h{1} = r0{1} = h{2}` (coupled)
- `c{1} = c{2}` (same ciphertext)

For the a2 call, I need to show the adversary produces the same result when the oracles differ at `r`. The adversary can query `r`, which would cause different responses, but then `r` ends up in the query log.

I think the right approach in EasyCrypt is to use a `call` statement with an invariant that tracks either the bad event (where `r` was queried) or the case where the query logs match and the maps are equal except at `r`. The oracle needs to preserve this invariant and return the same result on both sides. When the bad event holds, the query log is monotonically increasing, but the LRO maps could diverge completely, which creates a problem for showing equal responses.

I'm realizing I need to be more careful about what the invariant actually guarantees. Let me refine it to ensure the oracle can always return equal results: the query logs must always be equal, and the LRO maps must agree except possibly at `r`. This way, when the oracle is called with any input other than `r`, both sides return the same value from their respective maps. The issue is that when the oracle is queried at `Game1.r{2}`, the left side returns a stored value while the right side samples fresh, causing `={res}` to fail even though `eq_except` is preserved. Since `call (_ : Inv)` requires both invariants, this approach won't work. I need to explore other EasyCrypt tactics for handling oracle calls with mismatched responses.

Maybe I should step back and use a probability-based argument instead—showing that the games are close by bounding the probability of a bad event occurring, then using union bounds to relate the two games. But that would require introducing auxiliary games, which gets messy in an interactive proof. Let me backtrack to the pRHL goal before the `seq` cut and try a different tactic-level approach.

Actually, I'm wondering if EasyCrypt has a "call with bad event" variant that lets me specify when the call might break the `={res}` invariant. I vaguely recall seeing something like a call tactic that takes a bad event as a parameter, where the oracle preserves the invariant when the bad event doesn't occur, and preserves monotonicity of the bad event otherwise. Let me explore that syntax.

I'm going to try submitting a call with my invariant and see what subgoals EasyCrypt generates, even if some might be unprovable due to the `={res}` requirement.

Before that though, I need to handle the encryption part first. The current goal has encryption statements followed by the a2 call on both sides, so I should use `wp` to work through the deterministic code and then apply `call` for the a2 invocation. Since `call` requires the code after it to be empty or just a return, I need to check if that's the case here. I'm realizing the invariant needs to account for the bad event where `Game1.r{2}` appears in the query log, otherwise the oracle obligation will demand `={res}` even in cases where that shouldn't hold. Let me try incorporating that disjunction into the invariant so the `call` tactic can properly handle the different branches. ~ O {Inv}` with the `={res}` constraint folded into `Inv` differently.

Actually, in EasyCrypt, the standard `call (_ : Inv)` for an adversary with oracle `O` generates:
- `equiv [O.method ~ O.method : Inv ==> Inv /\ ={res}]`

This is the standard form. The `={res}` is required for the oracle method.

Since our oracle doesn't always produce `={res}`, this won't work.

Let me think about alternative approaches...

Alternative 1: Use `while` or `hybrid` arguments.

Alternative 2: Undo and restructure the proof.

Alternative 3: Find a way to make the oracle produce `={res}` even in the bad case.

For Alternative 3: The trick is to NOT have the left's LRO.m differ from the right's. If I can avoid storing the encryption hash in LRO.m on the left, the oracles would be identical.

I could modify the left program so that the LRO.o call during encryption is replaced with a fresh sample, just like the right. Then the LRO maps stay equal. But the program is fixed by the lemma statement, so I can't change it.

Alternative 4: Use `eager` sampling to rearrange when random sampling happens. If I eagerly sample the LRO value for `r` at the point when the adversary queries it instead of during encryption, then both sides sample `h <$ dptxt` without modifying LRO during encryption, and only when the adversary queries `r` during the a2 call does the left side's LRO get updated.

Let me try a different approach using `conseq` to adjust the postcondition. I could replace the postcondition with something simpler that establishes a relationship between the states, like saying either `b'` is equal on both sides or `r` is in the query log on the right side.

But I'm not sure that actually helps since the core problem is still the oracle call itself. Let me look into EasyCrypt's "up to bad" reasoning for oracle calls—there might be a `call` variant that takes both a regular invariant and a bad-event invariant as parameters.

Writing call syntax...

Actually, maybe I'm overcomplicating this. What if I sidestep the oracle equivalence entirely and use a different strategy: if the adversary already queried `r` during the first phase, the postcondition is satisfied immediately, so I only need to handle the case where it hasn't been queried yet. Writing equivalence proof...

Actually, I'm overcomplicating the tactic structure here. Let me step back and try a simpler approach using case splitting on the conditional instead of wrestling with complex postconditions in the `call` tactic. I need to clarify what the actual goal is here—whether I'm trying to prove equivalence for just the encryption step or the entire suffix including the `a2` call. Looking at the current goal state, I can see the left side has the full sequence with sampling, conditionals, and the adversary call, while the right side has a simplified version with direct sampling and the same adversary invocation. The precondition should establish what needs to hold before this suffix begins.

For the postcondition, I'm considering using `conseq` to reformulate it as a disjunction: either the values of `b'` are equal across both games, or the random value sampled in game 2 appears in the query log. This would be sufficient to prove the original postcondition since if `b'` values match, we're done, and if the random value is in the log, that's the failure case we're tracking.

The challenge is that this reformulation is essentially what we're already trying to establish, so the real obstacle remains handling the oracle call itself. I'm now exploring whether EasyCrypt's `call` tactic supports a syntax where I can directly specify both an invariant for the oracle and a post-relation for the main call in one step. I need to ensure the maps have identical domains and values, which would guarantee the oracle produces equal results. But this invariant breaks down after encryption since `Game1.r` exists in one map but not the other, creating a domain mismatch.

I'm hitting a dead end with this approach, so let me step back and try a different tactic entirely—maybe using an eager evaluation strategy or reasoning at the module level instead of trying to force the pRHL judgment through `byequiv`.

Actually, I should go back to the original goal and apply the fundamental lemma of game-playing directly. This lemma states that if two games are identical until some bad event occurs, then the probability difference is bounded by the probability of that bad event. In EasyCrypt, this "up to bad" reasoning framework should let me show that the two modules are equivalent up to a distinguishing event, which gives me exactly the bound I need. are equivalent except when a specific event (bad) occurs, and that bad event has the same probability in both modules—this is typically formalized with something like `equiv_upto` or `equiv_bad` in EasyCrypt.

Let me think about the practical approach here. I've already committed some tactics, so let me reconsider my decomposition strategy. Instead of inlining `LRO.o` on the left side, I could leave it as-is and call `LRO.o(r)` directly, which would make the structural difference between the two programs clearer. But since I've already done the inline, I should use `undo_to_checkpoint` to backtrack to an earlier point and try a different approach altogether.

Looking at what I've committed so far: I have the initial `have` statement setting up the probability bound, then the `byequiv` tactic with the structural equivalence, followed by inlining the keygen and enc procedures, inlining `LRO.o`, using `seq` to rearrange, and then `sim` for the prefix. After that, I closed the keygen subgoal with `inline *; wp; rnd; auto`. But I'm confused about how many goals remain—I should have the suffix subgoal plus potentially three others from the original `byequiv` and `have` statements.

Let me trace through this more carefully. The `have` tactic created two goals: proving the claim itself, and using it to finish the original goal. Inside the claim, `byequiv` split things into four goals (the pRHL equivalence plus side conditions). So that's 4 + 1 = 5 total. After working through the prefix with `proc`, `inline`, `seq`, and `sim`, I closed one subgoal with the automation. Now I need to figure out which goals are actually left and what they represent. I'm getting tangled up in the goal count, so let me just focus on what's in front of me. The current goal is the suffix subgoal with the encryption and a2 part, and I think I should backtrack and undo the inlining and seq cut so that the suffix still has the `h <@ LRO.o(r)` call instead of the expanded conditional.

Then I could use `call` to handle both the `LRO.o` call and the `A(Log(LRO)).a2(c)` call together. But undoing multiple steps is tricky—I'd need to use `undo_to_checkpoint` to see what's available, though that might lose a lot of work. Let me think about whether I can actually make progress on the current goal as it stands, or if I should try a different approach entirely, like using a `have` chain within the pRHL proof to establish the postcondition. Actually, I'm not even sure if `have` works inside a pRHL proof in this system.

Let me try splitting the suffix with `seq` instead, separating the encryption statements from the a2 call. I'll use a seq split that divides the left side at statement 9 and the right side at statement 4, with a mid-invariant that captures the equality of `b, c, glob A` along with the disjunction about whether the game result is in the log or the oracle maps match except for that result.

Actually, in the bad case `c` might not be equal between the two sides, so I need to adjust the invariant—only requiring `c` equality in the good case where the log queries match. After this split, both remaining programs are identical calls to the adversary's second phase, so they should be straightforward to handle.

For the postcondition, the bad case is trivial, but the good case requires the oracle to produce matching results when not querying `r`, which brings back the oracle consistency issue. I'm wondering if I can use case splitting in EasyCrypt's pRHL to handle the two scenarios separately, though I'm not certain that tactic is available.

Let me try a different angle: what if the call invariant just tracks that the query logs match and the random oracle's map is equal except for the bad predicate? Then for the oracle obligation itself, I'd need to prove equivalence with matching results, but that breaks down when `x = Game1.r{2}`. The key insight might be to couple the oracle responses even in the bad case—both sides would sample and store new values when the query isn't in their respective maps, or read existing values if it is.

The issue is that when `x = Game1.r{2}`, the left side finds it in its map and returns the stored value, while the right side doesn't have it yet and samples fresh. They diverge. I could argue the adversary sees different values but the bad event in the main call's postcondition accounts for this discrepancy. However, EasyCrypt's `call (_ : Inv)` syntax requires `={res}` for every oracle method—there's no flexibility there. I think the real solution is to use an `upto bad` equivalence instead.

Let me check if EasyCrypt has a tactic for this. There's probably a `bd_hoare` approach or a dedicated `upto_bad` lemma. Actually, I recall there's an `eager` tactic that handles lazy-to-eager transformations, and maybe an `eager if` variant for conditionals. That might help move the sampling past the conditional check. But let me try something more direct first—just attempt the `call` with a simpler invariant tracking the query log and LRO state, even though I know the maps will differ, and see what subgoals emerge.

The issue is that the precondition won't support the full invariant I need. Let me pivot to using `conseq` to weaken the goal instead. Or maybe I should use `case` to split on whether the sampled value appears in the query log—that would separate the bad event case from the good case where the programs behave identically.

In the bad case where the value is in the log, the postcondition becomes trivially true and I can close it automatically. But I need to be careful about the timing: `Game1.r` is a module-level variable assigned during `Game1.main()`, so I have to account for when it gets set relative to the precondition.

Actually, I realize the real issue is that at the start of the suffix, `Game1.r{2}` hasn't been assigned yet—it only gets its value from the `drand` sampling in the right program's first statement. So I can't case-split on whether it's in the log before that assignment happens; I need to do the case-split after the sampling occurs.

This is getting complicated with the manual pRHL decomposition. Let me step back and try a completely different approach using EasyCrypt's `byequiv` tactic with the `: bad_event` annotation in a different way.

I'm wondering if the `byequiv ... : bad` syntax actually works but I was just using the wrong variable names or expressions. The goal is to prove the inequality with the bad event being `Game1.r \in Log.qs`. Let me try formulating the byequiv call with just the postcondition `={res}` and the bad event as a separate clause.

Actually, I'm realizing that `byequiv` with the `: bad` annotation should automatically weaken the obligation to `!bad{2} => ={res}`, so I shouldn't need to write the implication explicitly in the postcondition. Maybe that's where I went wrong before—I was being too explicit when the tactic handles it automatically. But undoing all this progress feels like a lot to lose, so let me think about whether it's worth trying again.

Actually, let me try a different approach for the oracle call. I think EasyCrypt might support passing a bad event directly to the `call` tactic, or maybe it's part of the `equiv` declaration itself. I'm not entirely sure of the exact syntax, but I could try something like providing the bad event as an argument or using a disjunctive form in the invariant. Let me experiment with the current setup and see what happens.

If that doesn't work, I could try handling the encryption part step by step using `wp` and `rnd` tactics to work through the deterministic assignments, random sampling, and conditionals. Or I could backtrack and try a different `byequiv` syntax with the bad event, though that would mean redoing some work. Let me try to tackle the oracle call with a specific tactic sequence and see what subgoals it generates. I'm trying a different approach using `seq` to split the proof at the point where both sides have sampled their random values, setting up a precondition that equates the sampled values and other key variables. Now I need to analyze what happens in the remaining programs when the sampled value isn't in the domain of the logging oracle. I'm running into the same issue repeatedly—the oracle call requires different LRO maps between the two games, which breaks my proof strategy. Let me step back and try a completely different approach using EasyCrypt's `phoare` framework instead of the current decomposition. Actually, before abandoning this, let me attempt to prove the oracle subgoal directly by setting up the call with an invariant that tracks whether we're in the log or handles the map difference case.

If I can get the oracle subgoal to appear, I might be able to prove `={res}` by carefully coupling the right side's fresh sample to match the left side's stored value—essentially using a bijection in the random sampling to force equality between what the left reads from its map and what the right generates fresh.

But there's a fundamental problem: the left side doesn't actually sample anything when answering the query—it just retrieves a deterministic value that was stored earlier during encryption. The right side samples fresh from the distribution. I can't couple a deterministic read with a fresh random sample and expect them to be equal with probability 1. The value on the left was indeed random when it was first sampled and stored, but by the time the adversary queries it, that value is fixed and independent from the right's fresh sample, so they'll only match with probability `1/|dptxt|`. This means `={res}` genuinely fails here, confirming that the standard oracle pattern won't work for this proof.

I need a different approach. What if I use the `eager` tactic to move the random sampling from the encryption step into the oracle call itself? This would transform the lazy random oracle into an eager one, where the value gets sampled only when queried rather than precomputed during encryption. The challenge is figuring out how to apply `eager` correctly in this context, since it typically works on specific `equiv` goal structures. Let me reconsider whether there's a simpler way to restructure this. I'm considering using `sim` with an invariant instead of `call` to handle the structural differences between the oracle states, though I'm uncertain about the exact syntax for specifying the invariant. Let me try a practical approach and test `call` with a disjunctive invariant to see what obligations it generates.

Actually, I need to think through the order of operations here—the encryption happens before the adversary call, so I should work backwards from the call using `wp` to understand what precondition I need for the code that comes before it. When I apply `call` with an invariant, EasyCrypt will process the final call and leave me with a subgoal for everything preceding it, where the postcondition becomes the call's precondition.

For the adversary call to go through, I need to establish that the arguments and adversary state are equal along with the oracle invariant. But in the bad case where `c{1} ≠ c{2}`, the argument equality fails—so I can't use the standard `call` tactic directly. I might need to reformulate this so the argument inequality is absorbed into the invariant itself rather than being a separate requirement.

Alternatively, I could use `conseq` to adjust the postcondition: if I only need to prove `Game1.r{2} \in Log.qs{2}` in the bad case, then I don't have to establish equality for `b'`. But the issue is that `call` enforces argument equality regardless of what the postcondition is.

The real problem is that EasyCrypt's standard `call` tactic doesn't naturally handle "up to bad" reasoning for adversary oracle calls—this needs a more specialized technique, likely involving intermediate games that bridge the gap between the two executions.

Let me backtrack and try a different decomposition entirely. I'll undo to the checkpoint before the `seq` split and attempt a wholesale approach using `sim` instead, which might handle the encryption and second adversary call together without forcing the intermediate split.

Now I'm reconsidering the core issue: the oracle calls use different LRO maps on each side. What if I don't inline `LRO.o` on the left? Then the left keeps the actual oracle call while the right uses the sampled random value, and I can work with that asymmetry directly rather than trying to force them into the same form first.

Actually, maybe I should try a more direct tactic—undoing back to before the seq and using aggressive simplification tactics like pushing through deterministic assignments and random samplings to see what structure emerges underneath.

But I'm realizing the core issue: I can't reason about the adversary's behavior in terms of its oracle responses without access to its code, and the `call` tactic is meant to handle exactly this kind of abstract adversary reasoning.

The real problem is that after encryption, the left oracle stores an extra entry in the log, breaking the equality I need. What if I modify the left program to skip storing the hash result in the log altogether? That way I could avoid the mismatch without needing to inline the oracle call. the `if` branch executes and `h` becomes a fresh sample. Removing the `LRO.m` update would change semantics, but it doesn't matter in the good case since the bad event triggers whenever the adversary queries `r` later. This is the core "up to bad" reasoning, and I suspect EasyCrypt's standard `call` tactic doesn't handle it—I need to find a specialized tactic that does.

Let me search for EasyCrypt's `upto` tactic or similar constructs in the codebase. I could try using `upto` directly or with specific oracle constraints, but I'm not certain of the exact syntax. Actually, let me step back and try a completely different proof strategy instead of the `have` + `byequiv` decomposition. I'll attempt a direct `byequiv` statement that establishes equivalence under the condition that the bad event doesn't occur. Writing byequiv syntax... I'm trying to figure out whether EasyCrypt's `byequiv` tactic with the `: bad` form works on `<=` goals or only equality goals, since that would change how I structure the proof. Rather than get stuck on this detail, I should just try a few different approaches and see what the system accepts. Instead of undoing my work, I'll try introducing an intermediate claim that splits into two cases: either the states stay synchronized with the LRO maps close enough, or the bad event occurs. For the synchronized case I can use a call tactic with the appropriate postcondition, and for the bad case the goal should follow from program termination. The tricky part is figuring out how to actually case-split within a pRHL goal. I need to think through the order of operations here—`sp` processes deterministic statements from the start, but it stops once it hits a random sampling operation, so I can't use it to skip past the random `r <$ drand` on the left. Maybe I should process the two deterministic assignments first with `sp 2 0`, then handle the coupled random sampling separately with `rnd`.

Let me just try running `sp` and see what state it leaves me in, then I can use a sequence coupling tactic on the resulting random samplings before case-splitting on whether the random value appears in the log.

Actually, I should stop planning this out mentally and just start trying tactics to see what EasyCrypt accepts. Let me attempt the procedure call with the preconditions I need to establish about the log and the random value, using a tactic that handles the encryption and subsequent steps.
