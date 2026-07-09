# Tree-0.1.0 · turn 1 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:54:59.125Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} LRO.o.`

---

Let me analyze the current proof state carefully.

I'm proving `pr_Game0_Game1` which states:
```
Pr[BR93_CPA(A).main() @ &m: res]
  <=   Pr[Game1.main() @ &m: res]
     + Pr[Game1.main() @ &m: Game1.r \in Log.qs].
```

The prefix already applied:


1. `byequiv (_ : ={glob A, glob LRO} ==> ={res} \/ (Game1.r \in Log.qs){2}) => //.`
2. `proc.`
3. `inline BR93(LRO).keygen BR93(LRO).enc.`

Now I'm setting up a pRHL goal to compare the two game programs side by side. I need to inline the BR93 operations and examine how the left and right sides diverge, particularly tracking when `Game1.r` enters the logging oracle's query set. Continuing with the game logic...

The key structural difference is how the key generation and message selection are handled—the left side samples and then destructures separately, while the right side does it in one step, and the left side explicitly binds `pk0` before using it in the ciphertext computation. The postcondition shows that the adversary's guess is correct either when both games produce the same result or when the random value leaks into the query log.

The critical insight is that replacing the random oracle call with a direct sample from the plaintext distribution is valid precisely when the input hasn't been queried before—if it has, we're in the bad event where the oracle's previous answer matters. The attempted proof tactic using the parent's call didn't work out, so I need to reconsider the approach.

Rather than trying to force a call tactic, I should think about using seq to establish equality at key checkpoints, then handle the divergent section where the oracle behavior differs from the direct sample. The final adversary call can come after we've resolved the middle game hop. I need to reconsider the constraint more carefully—the instruction forbids `call` entirely, but suggests `inline` as the main alternative. Let me explore three approaches: inlining the oracle and assignment operations directly, using `seq` to break the proof into manageable pieces, or specifically inlining the `LRO.o` oracle call to expose its body and match it against the direct sampling on the right-hand side. I'm comparing how the left and right programs execute through their first several steps to find the right decomposition strategy.

The programs diverge when the left side samples `r` from `drand` and queries the lazy RO at that point, while the right side samples `r` and `h` independently. The crucial observation is that if the right-hand side's `r` value hasn't been queried in the log yet, the lazy RO will return a fresh random sample from `dptxt`—exactly matching what the right side does directly. So I can structure the proof around this "up to bad event" argument.

For the EasyCrypt tactics, I need to handle the abstract adversary modules carefully. Rather than trying to inline everything upfront, I should use `call` to reason about the adversary's abstract calls, then focus on the oracle behavior and sampling equivalence where the actual divergence occurs. calls - we can't inline them, and the standard way to handle them is `call`. 

Hmm, but the instruction specifically says I shouldn't use `call`. Let me reconsider...

Actually, re-reading the instructions more carefully:

"These approaches led to a dead end. You MUST try a fundamentally different approach:
- Do NOT use `call` or any variation of it"

But `call` is THE standard way to handle abstract module calls in EasyCrypt pRHL. Without `call`, the only other option is... `sim`? But `sim` requires identical module bodies.

Wait - the failed tactic was specifically a 3-argument eager/bad-event form of call on the outer a2 call. Maybe I should try a different decomposition strategy instead.

What if I use `seq` to cut before the divergence point and establish the state relation, then inline on the left side and handle things at a lower level with `wp`, `rnd`, `skip`, etc.? For the final `A.a2` call, I'll eventually need `call`, but maybe the instruction means I shouldn't repeat the same pattern that failed. Let me think about what the correct proof structure should be based on the standard BR93 theory approach. I need to reconsider the postcondition more carefully—after the divergent section, both sides have the same remaining program, so I need to establish either state equality with matching arguments and globals, or that the bad event has already occurred in the second game.

The "up to bad" pattern with a 3-argument `call` is designed for exactly this situation, but since that approach failed, I should look at why the parent's attempt was rejected—the error indicates that the invariant I specified is missing conjuncts that the proof system needs to keep live.

The real issue is that using `true` as the "good" invariant is too weak because it doesn't preserve any state equalities, so I need a stronger invariant. But since I'm constrained from using `call`, I'm considering whether I can handle this entirely with `seq` cuts and `inline` tactics instead. However, I'm realizing that for abstract module procedures in EasyCrypt, `call` is actually unavoidable—there's no alternative way to reason about procedures like `A(Log(LRO)).a1`.

That said, `sim` might work for portions of the proof since both programs call the same adversary with the same oracle. Looking back at the alternatives, using `call` with a different invariant form is actually permitted, so I can try a mixed approach: use `seq` to handle the prefix, apply a standard `call` with an equality invariant for `A.a1`, work through the middle section with `inline` and low-level tactics, then use a 2-argument `call` form for `A.a2`.

The real challenge is that the postcondition has a disjunction—it's an "up to bad" style where I either show the executions are equivalent or demonstrate that the bad event occurred. For the `A.a2` call, I need the bad-event form of `call` with a "good case" invariant and a bad event condition, but the parent's attempt with that form likely failed because of how the condition was structured.

Let me reconsider the whole approach. Instead of trying to force the bad-event pattern, what if I start fresh by inlining the initialization calls on both sides since they're identical, then work through the divergent sections more carefully? Since I can't use `call`, I'll rely on `inline` to expand what I can and handle the middle section where the programs diverge. I need to work through the proof structure systematically—handling the initialization, keygen sampling, and the adversary calls in sequence. The tricky part is managing the bad event threading through the second adversary call, so I'll try cutting the program with `seq` and then applying tactics step by step to see what works. First, let me load the MCP tool to submit proof attempts. I'm identifying where the two games diverge: the LHS has several extra assignments after the common initialization steps, so I need to use `seq 7 4` to cut right after both games have set up their shared state. At that point, the invariant should track the adversary's state, the query log, the LRO memory, the bit `b`, the two messages, and the public key. Writing proof structure... The diagnostic reveals that the precondition needs more conjuncts than just `={Log.qs}` — it also requires `={LRO.m}` and possibly others that ProgramIR keeps live at this call site. So I'd need something like `call (_: ={Log.qs, LRO.m}, (Game1.r \in Log.qs){2}).` to capture the full invariant, but since I'm told not to use `call`, I need to find a different tactic.

Let me explore alternatives: maybe a case split on whether `Game1.r \in Log.qs` would work better — in the true case, the postcondition's right disjunct is satisfied immediately and I just need to show losslessness for `A.a2`, while in the false case I can prove full equivalence. Though case splits in pRHL are awkward. Or perhaps `sim` could handle the equivalence automatically after some setup.

Actually, I'm realizing the core issue: after establishing `c{1} = c{2}` or the bad event, both sides call the same module `A(Log(LRO)).a2`, but `sim` won't work with a disjunctive postcondition. I think I need to step back and try something fundamentally different — maybe inlining the LRO operations on the left side first.

So my new approach is to inline `LRO.o` to expand the random oracle call, then work bottom-up with `wp` and `rnd`, and handle the adversary calls with simple equality invariants rather than the bad-event form.

After inlining, the left side shows the full body of `LRO.o` explicitly—when `r` isn't in the domain, we get a fresh sample from `dptxt`, which matches the right side. But there's a subtle issue: `r` is sampled differently on each side, and the query logging through `Log(LRO)` doesn't capture the direct `LRO` calls that happen inside `BR93(LRO).enc` when it invokes `H.o(r)`. So I need to track where that query `r` actually goes.

The adversary's queries through `Log(LRO)` are logged, but the encryption query inside `BR93` bypasses the logging wrapper entirely—it goes straight to `LRO`. Looking at the code structure, `BR93(LRO).keygen()` and `BR93(LRO).enc()` both use `LRO` directly, not the logged version, while the adversary only sees `Log(LRO)`.

This means the random value `r` used in encryption won't appear in `Log.qs` unless the adversary happens to query it independently. After inlining, if `r` isn't in the logged queries, then `h` from `LRO.o(r)` will be a fresh random value. I'm realizing the key distinction: `dom(LRO.m)` tracks all queries to LRO regardless of logging, while `Log.qs` only captures queries that went through the Log wrapper. The encryption query from BR93 hits LRO directly, so it's in `dom(LRO.m)` but not `Log.qs`, meaning `r` could be in the domain without being logged. This breaks my earlier assumption that these sets were equivalent.

Now that the encryption is already inlined, I need to reconsider whether I can further inline the LRO.o procedure itself on the left side. Let me look at what LRO.o actually does...

Examining the LRO procedure definition...

If I inline this procedure directly, I'll get the explicit conditional logic and can reason precisely about when sampling occurs. The key insight is that after the adversary's first phase runs through the logged interface, the domain of LRO.m contains exactly the queries that were made, so I can establish that a value is in the map if and only if it was queried during that phase.

Now looking at what happens at the encryption point: when the queried value hasn't been seen before, both sides sample fresh from the distribution, so they're equivalent; but when it has been queried, the left side returns a stored deterministic value while the right side always samples, which is where the difference emerges.

For the proof strategy, I need to carefully sequence the tactics: first cut at the common prefix before divergence, then inline the oracle operation on the left, analyze the cases based on whether the query's been logged, and handle each branch separately. The key is managing this in EasyCrypt with the right tactic ordering—I should start by inlining the initialization calls that appear on both sides, then work through the case split. I need to check what proof tactics are available to me—looks like I can only commit tactics, finish, restart, or undo, with no inspection allowed. So I'll have to work with what I know about the goal structure.

My strategy is to use a `seq` tactic to split the proof at the common prefix between the two sides, then handle the prefix separately from the divergent part where the interesting differences occur. Let me start by loading the tool and carefully mapping out the statement numbers so I can construct the cut correctly. I'm verifying that the cutoff point after statement 7 on the left and statement 4 on the right correctly identifies where the two games diverge. At this point in the execution, the adversary's state, logged queries, oracle state, bit selection, and key material are all identical between the two games, which establishes the invariant needed for the security argument. I need to verify that the module variable syntax works in EasyCrypt—`={Log.qs}` and `={LRO.m}` should be valid for referencing those specific variables. For the prefix subgoal, I'm proving that after both sides initialize the log and oracle, the postcondition holds with all the necessary equalities and the message selection based on the bit. if b{1} then m0{1} else m1{1}. The tricky part is coupling the key sampling since the left side samples a single key while the right side samples a pair—but since they're both drawing from the same distribution, EasyCrypt's `rnd` tactic should handle this. For the prefix, I'm thinking I can use `inline` to expand the initialization calls, `wp` for the deterministic steps, `rnd` for the random samplings, and `call` for the A.a1 invocation since it's identical on both sides and doesn't touch the key generation.

Wait, I need to reconsider the constraint about not using `call`. The prohibition actually allows `call` with a different invariant structure—so it's not that `call` is forbidden entirely, just that the specific form that failed before won't work. Let me look at what went wrong: the previous attempt used a particular invariant shape that led nowhere, so I need to try a different invariant formulation with `call` rather than abandoning it altogether.

For the A.a2 case, instead of repeating that failed pattern, I should establish the right equality or membership condition at the point where both sides reach those calls, then apply `call` with a simpler, more direct invariant—either a standard equality invariant or a membership condition that actually constrains what I need. call (_: ={Log.qs, LRO.m}, (Game1.r \in Log.qs){2}).

The issue is that the invariant needs to account for everything the oracle preserves — just tracking `Log.qs` and `LRO.m` isn't enough. The oracle also modifies other state when it calls `LRO.o`, so I need to figure out what additional equalities or properties must hold for the call tactic to accept the invariant as sufficient. Game1.r \notin Log.qs{2}`
- Should include `={LRO.m}` (so the oracle returns the same values)
- Should include `={Log.qs}` (so the query log stays in sync)

The tricky part is figuring out what "conjuncts ProgramIR keeps live" actually means—maybe it's `={glob A}`? But that doesn't make sense since the oracle call doesn't modify glob A. I'm realizing the real issue might be that `Log(LRO).o` has two procedures, and when I call a module with oracle access, I need invariants for all accessible procedures. So for `A(Log(LRO)).a2`, I need to provide invariants for the oracle that A can access.

I'm trying different approaches with the call tactic—maybe using `conseq` to split the disjunction instead of the 2-arg bad-event form. At this point I should just start running tactics and see what errors the proof manager gives me.

Writing EasyCrypt tactics... me try this plan:

1. `seq 7 4 : (...)` — split at common prefix
2. Handle prefix subgoal
3. For the remainder:
   a. Inline `LRO.o`
   b. `wp` + `rnd` for the samplings and deterministic assignments
   c. For A.a2: try `call (_: ={Log.qs, LRO.m}).` — but this doesn't handle the disjunction...

Actually, wait. Let me think about this differently. After the seq cut, the second subgoal has postcondition:
```
(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})
```

And the remaining programs are:
LHS:
```
r <$ drand
h <@ LRO.o(r)
c <- (f pk0 r, h +^ m)

b' <@ A(Log(LRO)).a2(c)
```

RHS:
```
Game1.r <$ drand
h <$ dptxt
c <- (f pk Game1.r, h +^ if b then m0 else m1)
b' <@ A(Log(LRO)).a2(c)
```

For the A.a2 call, the postcondition involves a disjunction. If I can establish `c{1} = c{2} /\ ={glob A, Log.qs, LRO.m}` before the call, then using a call tactic with the postcondition `={Log.qs, LRO.m}` would give me `={b', glob A, Log.qs, LRO.m}`, and combined with `={b}` from the seq cut, I'd get the equivalence `b'{1} = b{1} <=> b'{2} = b{2}`.

But I can't always establish `c{1} = c{2}` — only when `Game1.r` wasn't previously queried. When it was, the LRO values might differ. So maybe I need to establish `c{1} = c{2} \/ Game1.r \in Log.qs{2}` instead, but that creates a circular dependency.

The standard 2-argument bad-event approach is probably the right way. Let me try working backwards from the full goal instead of splitting with seq first.

Now I'm looking at the final statements where both sides call `A(Log(LRO)).a2(c)`. I need to set up a call tactic with the right precondition about the oracle preserving the log and LRO state when the random oracle hasn't been queried yet. Let me start trying tactics and see what the system accepts. I see the alternatives actually do allow `call`, just in a different form—either 2-arg standard form or some other variant instead of the 3-arg bad-event form the parent used. With a 2-arg `call`, I'd establish the precondition that the arguments and relevant globals match between the two executions, then after the call I'd get matching results that satisfy the left disjunct of my postcondition.

The catch is that this only works when the RO call produces the same result in both executions, which requires the random oracle hasn't been queried yet. So I need to do a case split before the call—one branch where the RO hasn't been queried and I can use the standard `call`, and another branch where it has been queried and I handle that separately.

Now I'm realizing that EasyCrypt's `case` tactic behaves differently in pRHL, and trying to case-split on a disjunctive postcondition after `seq` might not work cleanly. Using `conseq` to weaken the postcondition doesn't really help either.

Let me try a different strategy: handle the common prefix with `seq`, then for the diverging part, inline the oracle on the left side and carefully manage the conditional logic. When calling A.a2, I'll use a simple form that couples the arguments and global state, but this creates a precondition I need to verify—specifically that the ciphertexts match and the relevant state is synchronized.

The key insight is that after inlining and simplifying, I reach a point where the outcome depends on whether the queried value is in the oracle's memory: if it's fresh on both sides, the ciphertexts match; if it's cached on one side but fresh on the other, they diverge but the bad event triggers. I need to express this case split using EasyCrypt's conditional tactics.

Defining the Lazy Random Oracle module... I'm comparing the inlined versions of both sides of the game now. On the left, the random oracle gets invoked with the sampled value, and then we construct the challenge. On the right, we're sampling the hash directly without going through the oracle, which is the key difference I need to track through the rest of the proof. I need to handle the case where the bad event holds for the A.a2 call. My approach is to split this into two parts: first, I'll establish the invariant that couples the global state and key variables across both sides, then inline the oracle call on the left to expose the remaining programs and work through the postcondition.

After inlining the oracle, I can see the left side samples randomness and conditionally updates the oracle map before retrieving the value, while the right side directly samples the hash value. The precondition ties together the adversary's state, query logs, oracle map, and the message bits across both sides.

Now I'm working backwards from the adversary's final call. I'll apply the two-argument call rule for equality to handle the A.a2 invocation, which should split this into proving the oracle's behavior preserves the relevant equalities, plus the main goal about the adversary's output.

The tricky part is that the postcondition requires either the bit equality or the event that Game1.r appears in the log. The two-argument call gives me the bit equality when both sides match, but in the failure case where the random value leaks into the log, the ciphertexts can diverge and I can't maintain that equality—I'd need to rely on the event condition instead.

I'm considering whether to split the proof into cases before calling the lemma: handle the good case where the ciphertexts stay equal, then separately discharge the bad case where the event holds. The challenge is that EasyCrypt doesn't have built-in support for case-splitting on disjunctive preconditions in the way I'd need. I'm wondering if a different tactic like `eager` might work better, or if I should avoid inlining the oracle call and use `wp` to reason about the deterministic assignment and merge differently.

Actually, what if I use `seq` to cut right before the A.a2 call, setting up an invariant that either the ciphertexts match or the bad event has occurred? Then for the remaining subgoal with just the A.a2 call, I'd have a pRHL goal where the precondition is this disjunction and the postcondition relates the outputs appropriately.

In the bad case, since Game1.r is already in Log.qs before A.a2 runs, and A.a2 can only add to that log, the bad event persists through the call. In the invariant case where the ciphertexts and shared state match, A.a2 executes identically on both sides, making the outputs equal, which satisfies the postcondition. The `call` tactic with bad-event form should handle exactly this pattern.

The diagnostic flagged that my attempted invariant was missing conjuncts that the proof system tracks at this call site. I initially tried just `={Log.qs}`, which was too weak. Let me strengthen it by including the LRO.m state as well, since that's also part of the shared context.

Now I'm realizing the distinction between the 2-argument and 3-argument call forms matters here. The parent used the 3-argument form with a bad event, which failed due to insufficient conjuncts. Maybe I should try the simpler 2-argument form instead, which just needs a postcondition without the bad event tracking.

But that creates a new problem: with a 2-argument call, I can't directly express the disjunctive postcondition. I'd need to handle that case split at a different level in the proof structure, either using `conseq` to transform the goal or by working with the disjunction at the `seq` level.

Looking at the postcondition more carefully, the bad event `(Game1.r{2} \in Log.qs{2})` on side 2 is what allows the equality to fail, so I need to figure out how to incorporate that into the proof strategy.

The standard approach in EasyCrypt for this kind of "up to bad" game hop is to use the bad-event form of `call` for adversary interactions and thread the bad event through the proof. My previous attempt failed because the invariant wasn't strong enough, so I'll try again with a complete invariant that tracks both `Log.qs` and `LRO.m` rather than just `true` or a partial invariant.

Actually, I'm realizing I was told not to use `call` at all. Let me reconsider the alternatives—either inlining the oracle directly or exploring different forms of `call` with a different invariant structure, possibly the 2-argument version or something related to P2.

Since the adversary `A` is abstract, I can't inline its methods `A.a1` or `A.a2`, so I'm forced to use some tactic like `call`, `sim`, or `proc` to handle those calls. Let me think about `sim` instead—it proves pRHL equivalence by showing programs are syntactically identical. If I can establish that all shared state is equal after the middle section, then `sim` should work on the `A.a2` call, except it can't handle the disjunctive postcondition. But I could use `conseq` first to weaken the postcondition to something simpler, then apply `sim`.

Writing proof tactic... I see the issue now — the two games aren't actually equivalent when the bad event occurs, so I can't just prove full equivalence and avoid the bad event handling. I need to use `call` with a stronger invariant like `={Log.qs, LRO.m}` to properly handle the bad event case, then structure the proof with a sequence of steps that maintains the right preconditions and postconditions.

For the first subgoal, I'll work through the initialization and deterministic assignments with `wp`, handle the random samplings with `rnd`, and use `call` for the adversary's first query. For the second subgoal, I'm setting up a `call` statement that tracks the relationship between the two games' random values and ensures the log state stays synchronized.

Now let me actually start working through this instead of planning further. I need to check the goal structure carefully — after splitting with `seq`, I should get the prefix as the first subgoal and the rest as the second. Let me begin and adjust as I go.

Looking at the current goal with calls on both sides, I'll try working backwards from the end. The `call` statement for A.a2 needs to establish that the log queries and LRO module state match, plus verify that the game's random value appears in the log.

Wait, this is almost exactly what the parent attempt tried with `call (_: true, ...)` and it failed. Let me reconsider the approach.

The diagnostic indicates that `call (_: ={Log.qs}, ...)` was also rejected because it's missing required conjuncts. The issue is that for the A.a2 call site with oracle Log(LRO), I need to generate subgoals that verify Log(LRO).o works identically on both sides. The invariant needs to be preserved by the oracle's operation and include everything necessary for it to function correctly — so `={Log.qs, LRO.m}` should work since prepending to the log preserves equality of the query set if it held before.

I'm wondering if the `call` tactic also requires some form of global state equality or argument equality that I'm not including, or if the precondition itself needs to be structured differently to satisfy what the tactic expects.

Let me just try submitting the first tactic and see what the error message tells me — that'll be faster than continuing to speculate about what's missing. I'll load the proof submission tool and start from the bottom of both programs, working with the final statements where both sides call `A(Log(LRO)).a2(c)`. I'll try:

```
call (_: ={Log.qs, LRO.m}, (Game1.r \in Log.qs){2}).
```

If this works, it should generate subgoals for the oracle and the main goal. Let me try it.

Actually hold on. The profile says the allowed proof intents are `commit_tactic`, `finish`, `fresh_restart`, `undo_last_step`, and `undo_to_checkpoint`. So `probe_tactic` isn't available — I can only commit directly, which means each tactic is permanent unless I undo. I need to be careful and commit confidently.

Let me think differently about this. The parent tried a bad-event call with a trivially weak invariant, so what if I start with `wp` instead? That would consume the deterministic assignment on both sides, though it would stop at the module call. Let me explore whether pushing past the assignments first gets me somewhere useful.

Actually, I should verify the goal structure first — the `call` tactic works on the last statements on both sides, and I need to confirm both are module calls before attempting it. So `wp` needs to clear any deterministic code after the call first, but since `A.a2` is the final statement, `call` should work directly on it. The postcondition tracks `b'`, `b`, `Game1.r`, and `Log.qs`, so applying `call` with a two-argument bad-event form should handle this — I'll try that approach instead of the three-argument invariant form the parent used. I've been going in circles on the exact syntax, so let me just load the tool and start experimenting—I'll adjust based on what happens. Looking at my options, I could split at the common prefix, try the call tactic with the bad event form, or inline the LRO.o call. The inline approach seems like the most different direction from what was already attempted, so I'll start there.

But I need to be careful about scope—inlining LRO.o globally would expand it everywhere, including inside the Log wrapper, which might not help. I should target just the specific occurrence on the left side, either by using a position-specific inline or by inlining statement 9 directly where the call appears. I'm realizing that `inline{2} LRO.o.` won't work on the RHS since there's no direct LRO.o call there—it's been replaced with a direct sample. On the LHS, `inline{1} LRO.o.` should work to inline that single call at statement 9, but I need to verify the exact structure of what I'm looking at. Expanding the inlined oracle on the left side...

Good, I have the tool loaded and the current workspace view confirmed. Let me analyze the goal and start my proof approach.

The current goal is a pRHL goal with:
- LHS: BR93_CPA(A).main (inlined keygen+enc)
- RHS: Game1.main
- Pre: `={glob A} /\ ={LRO.m}`
- Post: `(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})`


My approach is to diverge from the parent by inlining `LRO.o` on the left side first, then work through the proof structurally. The parent's `call` tactic on A.a2 with a bad-event condition didn't work out, so I'm reconsidering the strategy and looking at what the diagnostic revealed about the failed call attempt.

Instead of jumping straight to the bad-event call like the parent did, I'll use `seq` to isolate the common prefix first, then expand the random oracle call to make the code explicit before proceeding. Let me start with `inline{1} LRO.o` to unfold the oracle body and see what I'm working with.
