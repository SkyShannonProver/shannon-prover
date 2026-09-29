# Tree-0.1 · turn 4 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:38:42.825Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2} /\ ={Log.qs}, Game1.r{2} \in Log.qs{2}).`

---

Now I can see the full structure after inlining:

LHS:
```
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
(11) b' <@ A(Log(LRO)).a2(c)
```

RHS:
```
(1)  Log(LRO).init()
(2)  (pk, sk) <$ dkeys
(3)  (m0, m1) <@ A(Log(LRO)).a1(pk)
(4)  b <$ {0,1}
(5)  Game1.r <$ drand
(6)  h <$ dptxt
(7)  c <- (f pk Game
```

The RHS version is diverging from the LHS—it's sampling the random value and plaintext directly rather than going through the LRO oracle, and the ciphertext construction is incomplete in what I'm seeing.

The postcondition I need to establish is that the adversary's output matches in both games, or one of the games reveals the random value through the oracle's query log.

To prove this pRHL judgment, I should inline the lazy oracle logic on the LHS to expose what's happening, then use sequential composition to align the code paths. The tricky part is handling the `a2` call where the two oracles have different states—I'll need an "upto bad" invariant that captures when the games diverge based on whether the random value appears in the oracle's query log.

For the call tactic, I'm thinking about how to structure the invariant to handle both the good case where the oracles stay synchronized and the bad case where they diverge. Let me work through this step by step, starting with the deterministic steps and then tackling the oracle call with the right invariant. Writing oracle invariants... (Log.qs only grows). Left disjunct preserved.
- But we need `={res}`. If bad has already happened, the oracle states could have diverged arbitrarily, so `={res}` might not hold.
- THIS DOESN'T WORK with standard `call` because we can't guarantee `={res}`.

So standard `call (_: Inv)` doesn't work for "upto bad" reasoning because it requires `={res}` for all oracle calls.

In EasyCrypt, there must be a different mechanism. Let me think about this...

Actually, I think the right approach for "upto bad" in adversary calls is the "eager/lazy" technique combined with a module transformation, not a direct `call` with a disjunctive invariant. The key insight is that in both games, the adversary queries the random oracle through the same interface, but the difference lies in how the oracle values are computed—either lazily on demand or eagerly pre-sampled. If I use eager evaluation where all oracle values are pre-sampled, then for any random input, the oracle lookup returns a pre-computed value, and I can reason about the equivalence up to the point where the bad event occurs.

Alternatively, I could introduce an intermediate game with a flag that tracks when the bad event happens, showing that the games agree on all events when the flag isn't set, and bounding the probability of the flag being triggered.

Or I could try a more direct approach: instead of relying on `byequiv`, I'd use probability lemmas to decompose the success probability into cases where `r` is queried versus not queried, then bound each case separately.

The challenge is that `r` isn't directly accessible in G0, so I need to find a way to reason about it indirectly. Let me try inlining the oracle call on the left side to expose the conditional logic around the random sampling and map update, then case-split on whether `r` is already in the oracle's domain. The case where `r` was already queried by `a1` is straightforward—it means `r` is in the query log for both games, so the bad event triggers. The trickier part is handling the first case where `r` wasn't in the oracle's map at encryption time: after encryption, `a2` sees a different oracle state than `a1` did, and I need to carefully track what happens when `a2` makes queries through the logging oracle. query `x`:
  - If `x = r`: 
    - LHS: `LRO.m{1}.[r] = h` (exists, so return it, no sampling)
    - RHS: `r \notin dom(LRO.m{2})`, so sample fresh, set `LRO.m{2}.[r] <- h'`, return `h'`
    - Different results! But `r \in Log.qs` now, so bad event happens.
  - If `x \neq r`:
    - `LRO.m{1}.[x] = LRO.m{2}.[x]` (maps agree off `r`)
    - Same result. Maps stay in sync on `x`.

So for the `a2` call: either the adversary never queries `r` (and the results agree), or it queries `r` at some point and triggers the bad event. The real challenge is getting EasyCrypt's `call` tactic to work with this kind of upto-bad reasoning—I need to find the right invariant format that the tactic actually accepts. Let me step back and try a completely different approach using the `eager` tactic to pre-sample all oracle values upfront, which might make the proof structure cleaner. the encryption step just reads a pre-sampled value, which is equivalent to sampling fresh.

The `eager` tactic in EasyCrypt handles this kind of eager/lazy oracle transformation.

Actually, I think there's a much simpler approach. Let me re-read the proof structure.

Actually, maybe I should try the following approach:

1. Inline `LRO.o` on the LHS (for the encryption oracle call only)
2. Use `rcondt` or `rcondf` to handle the conditional
3. Align the remaining code

But `inline LRO.o` would inline ALL occurrences of `LRO.o`, including inside `Log(LRO).o` during adversary calls. That makes the proof much harder.

Hmm. Let me try `inline{1} LRO.o` at position to only inline the encryption-step oracle call.

In EasyCrypt, I can use `inline{1}` with a specific position number to target just the encryption oracle call. Let me count through the operations on the LHS to identify which call number it is—starting with the initialization, then the adversary's first phase, the bit sampling, and finally the random value generation before the oracle call. I need to figure out which `LRO.o` calls would actually be inlined. The explicit `h <@ LRO.o(r)` call at the encryption step should be inlineable, but the `LRO.o` calls nested inside the `Log(LRO)` wrapper—which get invoked through the adversary's procedure calls—are in a different scope and shouldn't be affected by inlining just that one explicit call.

Actually, I'm second-guessing this whole approach. Let me step back and try a completely different proof strategy instead—maybe splitting the inequality into separate parts with `have` and `byequiv`, or exploring EasyCrypt's `fel` tactic for failure event lemmas.

Wait, but `fel` is designed for bounding bad event probabilities, not for game-hopping proofs like this one. My actual goal has a different structure—it's about showing either the return values match or the bad event occurred.

Let me think about this more carefully. The postcondition essentially says the return values either agree or the bad event happened. For the `a2` call, I could try using a `call` tactic with an invariant...

Writing proof invariant... I'm working through the case where `x` equals the queried record — when the adversary queries a value that was encrypted, the two sides might produce different results, triggering the bad event since the record enters the query log. But this creates a problem: I need to show the results are equal even when the bad event fires, and that's where the proof breaks down in this sub-case.

The core issue is that standard invariant-based reasoning doesn't handle this scenario — I need either EasyCrypt's "upto bad" mechanism or a different approach entirely. Let me think about what EasyCrypt actually offers here, particularly around the `call` tactic and how it handles pre and postconditions. Writing the call syntax... I'm comparing how the two games handle the challenge computation—on the left side, I'm constructing it step-by-step with intermediate variables, while on the right side, I'm building it more directly in a single assignment, and then both games call the adversary's second phase with that challenge.

Now I need to work backwards through the proof structure: starting with the final call to `a2`, then handling the deterministic challenge construction, the random oracle query versus the plaintext sampling, the randomness for the challenge bit, the deterministic setup before that, the adversary's first phase, and finally the key generation and initialization.

Writing the proof tactics...

But I'm realizing the `call` tactic might not support the invariant and bad event syntax I'm trying to use, so I may need to restructure this approach entirely.

If I can't use `call` with that syntax, I could try inlining the abstract adversary directly, but that won't work since `A` is abstract. Alternatively, I could reformulate the postcondition to handle the bad event separation differently, or use a chain of `have` statements to decompose the probability bound instead of relying on `byequiv`.

Let me step back and think about what EasyCrypt technique actually handles this scenario: two games differing only in one step where a random oracle call is replaced with direct sampling, with the difference captured by a bad event. The standard approach in the literature is...

Actually, looking at the `call` tactic more carefully, I think the right syntax for "upto bad" reasoning involves specifying a good invariant and bad event, which generates several proof obligations: equivalence goals showing either the invariant holds with matching results or the bad event fires, plus monotonicity conditions ensuring the bad event can only be triggered, never cleared.

I'm not entirely certain of the exact form EasyCrypt expects, so I should just try running it and see what obligations it generates.

Actually, I'm wondering if the "upto bad" call might structure the goals differently—maybe with an equivalence goal for the coupling when bad hasn't occurred, a phoare goal to maintain either bad or the invariant, and stability conditions on each side. But I'm really just guessing at this point, so let me attempt it and see what EasyCrypt tells me.

Before diving in, I need to figure out how to handle the `a2` call next. Let me try a simpler approach first: what if I use `sim` for the parts that align and manually handle where they diverge? I could try asserting that after the initial setup steps—4 on the left side and 3 on the right—the key invariants hold, then work from there. Let me recount the actual steps more carefully based on what's in the code. I'm structuring the proof by separating it into three parts using sequence lemmas: a prefix that establishes the common setup through the random bit sampling, a middle section where the encryption diverges between the two games, and a suffix covering the adversary's final query. I need to carefully track which variables are equal across both sides at each boundary to set up the sequence conditions properly. I'm reconsidering the approach—maybe I should start with a simpler invariant like `={glob Log, glob LRO}` to see if EasyCrypt accepts it, which would tell me whether I need the more complex formulation. Let me try the call tactic with the detailed invariant that tracks the exception predicate on Game1.r{2}, the log entries, and ensures Game1.r{2} stays in the query set. I need to work through the proof strategy in EasyCrypt. The key insight is that when I use the `call` tactic on the adversary's final statement, it will generate a precondition I need to satisfy. So my approach should be: first apply `call` to handle the adversary invocation and oracle constraints, then work backwards through the encryption step, and finally establish the initial conditions. Let me try submitting this and see if the tactic syntax is accepted, keeping in mind that the postcondition requires showing either the adversary's outputs match or the random value appears in the log. After `call (_: inv, bad)`, the tool wants a precondition of `={c, glob A} /\ inv` and a postcondition of `(={b'} /\ inv) \/ bad`, which combined with `={b}` gives the desired result. Since there's nothing between the `a2` call and the procedure's return, the call's postcondition needs to directly imply the overall postcondition. I'm realizing I need to think through how `b` gets threaded through—the call sets `b'{1}` and `b'{2}` based on adversary outputs, and if the "upto bad" call gives `={b'} \/ bad`, then combined with `={b}` from the precondition, I get `(b'{1} = b{1}) = (b'{2} = b{2}) \/ bad`. To ensure `b` is available in the call's precondition, I should probably apply `wp` first to handle any deterministic steps afterward. the call's postcondition should give me either the equality of `b'` values across both sides along with the invariant, or the bad event where `Game1.r{2}` enters the log. Since the precondition already establishes `={b}`, if `={b'}` holds then both sides of the target postcondition are satisfied, and if the bad event occurs, the right disjunct is proven.

Now I need to verify the precondition before the call includes everything required: the equality of `b` and `c`, the adversary state, the oracle invariant, and the fact that `Game1.r{2}` is already set. Let me try submitting this with the "upto bad" syntax to see if the tactic can handle it directly.

Actually, I realize the issue is that the preceding statements don't match between the two sides — the `a2` call appears at different positions with different code before it. I need to align that earlier code first before I can use `call` to process the final statement. In pRHL, the `call` tactic processes the last call on both sides, but everything before it needs to be synchronized, which means I'll need to handle the mismatched preceding statements through other tactics first. ants
3. Then you prove the precondition using the preceding code

So `call` should work here — it processes `a2` on both sides (which is the last statement on both sides), generates the precondition, and then I prove the precondition with the remaining preceding code.

Let me try it. What would the call look like?

For the "upto bad" call:

```
call (_: eq_except (pred1 Game1.r{2}) LRO.m{1} LRO.m{2} /\ ={Log.qs}, Game1.r{2} \in Log.qs{2}).
```

Wait but I also need `={glob A}` as part of the invariant or call precondition. In EasyCrypt, `call (_: Inv)` for `A(O).f(x)` automatically includes `={glob A}` in the precondition and postcondition of the call (since the adversary is abstract and its state must be synchronized).

So the invariant `Inv` is just about the oracle's state. Let me try the call with my oracle invariant and see what happens — if the syntax is wrong, EasyCrypt will tell me. Actually, I should consider that the "upto bad" variant might have different syntax, so I'm thinking through a few possible options for how to structure this call.

I think the first option is most likely correct, so let me try that. Actually, I just realized the oracle invariant needs to capture that `Log.qs` is coupled between the two games, and since the oracle modifies both `Log.qs` and `LRO.m`, the invariant has to account for both. In the "upto bad" setting though, the invariant only needs to hold until the bad event occurs — once `Game1.r` appears in `Log.qs`, we stop caring about the coupling.

So the invariant states that when bad hasn't happened, the LRO maps agree except at `Game1.r`, and `Log.qs` is synchronized across both games. When the oracle is called with some input `x`, if `x` isn't `Game1.r`, then both sides behave identically because the maps agree at that point, they sample or return the same value, and both add `x` to `Log.qs` while preserving the map agreement.

But if `x` equals `Game1.r`, then `Game1.r` gets added to `Log.qs` on the right side, which triggers the bad event — and at that point I don't need to maintain the invariant anymore. This is the classic "upto bad" pattern where the oracle preserves the invariant and equality of results when the bad condition hasn't been triggered, then transitions to bad when it is.

Now I'm setting up the call in EasyCrypt. I need to generate an equivalence statement for each oracle procedure that maintains the invariant and the bad flag.

Defining oracle equivalence statements...

I need to verify both goals are provable: the equivalence maintains the invariant or reaches the bad state, and once we're in the bad state it persists. The oracle only modifies the log and map, so both should hold. I should also check whether EasyCrypt requires the oracle itself to be lossless for the "upto bad" reasoning, not just the adversary. Let me attempt the tactic and see what constraints arise. I need to think through how the `call` tactic will handle this asymmetric bad event that only exists on side 2. Let me try applying it directly and see what preconditions it generates, since I'm not sure if a preceding `wp` is even necessary in EasyCrypt for the final statement.
