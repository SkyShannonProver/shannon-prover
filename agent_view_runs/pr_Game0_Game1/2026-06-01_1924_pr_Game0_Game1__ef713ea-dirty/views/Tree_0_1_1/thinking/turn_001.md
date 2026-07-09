# Tree-0.1.1 · turn 1 · commit_tactic

<!-- session db364dba-374a-4d5e-a03e-0f24d9575646 · 2026-06-02T03:03:10.808Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 5 4: (={glob A, glob LRO, glob Log, pk, sk, m0, m1, b}).`

---

Let me analyze the current proof state carefully.

I'm proving `pr_Game0_Game1` which states:
```
Pr[BR93_CPA(A).main() @ &m: res]
  <=   Pr[Game1.main() @ &m: res]
     + Pr[Game1.main() @ &m: Game1.r \in Log.qs].
```

The manager has already replayed this prefix:
1. `byequiv (_ : ={glob A, glob LRO} ==> ={res} \/ (Game1.r \in Log.qs){2}) => //.`


2. Now I'm inlining the keygen and encryption procedures from the BR93 oracle, then calling the adversary with the appropriate precondition and postcondition about the log query.
3. The first case follows directly from the adversary's lossless property, while the remaining cases are handled by showing the adversary's output is lossless and the distribution of the plaintext is lossless.

Now I'm examining the pRHL goal after inlining, comparing the left side (BR93_CPA with inlined procedures) against the right side (Game1), where both initialize the log, sample keys and randomness, run the adversary, and compute the ciphertext components.

The main structural differences are that the RHS samples the random oracle output directly from the plaintext distribution rather than calling the oracle, and it computes the ciphertext with the conditional message selection inlined into the tuple construction. The pre-condition requires the adversary's global state and the oracle's memory to match between sides, while the post-condition states that either the adversary's output matches the challenge bit on both sides, or the RHS's random oracle query appears in the adversary's query list. because the oracle hasn't been queried on that input yet. The problematic case is when `r` has already been queried, which triggers the "bad event." The layer-move diagnostic suggests I need to find a higher-level abstraction—either a transitivity argument, a wrapper lemma, or an intermediate assertion—and potentially undo some of the procedure expansion to use the call/bridge structure more effectively. Looking at where we are now, after handling the adversary's second call, I need to figure out what callable lemma can address the remaining live call sites.

Now I'm working through the body equivalence step by step, aligning the two sides using sequential composition and inlining. The left side's first four steps correspond to the right side's first three: initializing the log, sampling the key pair, and making the first adversary call. Then both sides sample the bit, but the left side has an extra key assignment that I need to account for.

The critical difference emerges in how they handle the challenge ciphertext: the left side calls the random oracle directly, while the right side replaces that oracle call with lazy sampling from the plaintext distribution. This is the core "random oracle programming" transformation I need to justify. I'm considering how to structure the proof using `seq` to cut at the right points and potentially move between abstraction layers. I'm looking at the postcondition after the call tactic—it's saying the results are either equal or the bad event occurred. Rather than manually stepping through with sequential tactics, I should try a higher-level approach using `inline` to handle the initialization calls, then use `seq` and `auto` to align the remaining statements systematically. Defining the oracle procedure...

When I inline `LRO.o`, the conditional logic becomes visible: if the input hasn't been queried before, it samples fresh randomness and stores it; otherwise it returns the cached value. The crucial observation is that on the right-hand side, we're also sampling fresh randomness with `h <$ dptxt`, so these are indistinguishable when the adversary hasn't previously queried that particular input. The game hop works because any difference only emerges in the bad event where the input was already queried.

Now I need to be more careful about the timing: the adversary calls `A(Log(LRO)).a1(pk)` before we sample `r`, so `Log.qs` might already contain values from that initial call. The real question is whether the freshly sampled `r` happens to collide with something already logged. Let me structure the proof properly by handling each step of the game separately—first the initialization, then key generation, then the adversary's first call.

The key insight is that I should try inlining the lazy oracle `LRO.o` on the left side to see what the body actually does, which will help me understand how to bridge the two games. samples from `dptxt` when the key isn't in the map. Since `r` is freshly sampled, and the only way the key is in the map is if `r \in Log.qs` (approximately), we can argue:

- In the case `r \notin LRO.m`, the oracle samples `h <$ dptxt`, which matches the RHS.
- In the case `r \in LRO.m`, the bad event `Game1.r \in Log.qs` occurs.

Let me try a different approach. Instead of going step by step, let me try:

1. `inline{1} LRO.o.` — inline the oracle call on the left side
2. Then use `wp` to handle the final assignments
3. Then reason about the sampling

Actually, let me reconsider the approach. The "up" layer move suggests maybe I should try a completely different strategy from what the parent did.

Looking at the parent's approach: it used `proc; inline BR93(LRO).keygen BR93(LRO).enc; call (_: true, bad)` etc. So the parent already inlined and set up the eager/lazy argument. For the "up" move, maybe I should try to use `seq` to cut at a higher level, identifying the key invariant at an intermediate point.

Let me start by handling the identical `Log(LRO).init()` calls on both sides, then inline the initialization and use `wp` to push through the assignments. I'm laying out the exact statement sequences for both sides to spot where they diverge. The left side samples randomness and calls the oracle directly, while the right side uses a different random value and samples from the plaintext distribution instead. I need to align these carefully with a seq tactic to establish the right invariant before handling the branching logic. I'm trying to set up a sequence cut after statement 5 on the left side and statement 4 on the right side, which should be provable since the initialization, key sampling, the first adversary call, and b sampling are all equivalent. For the second part after the cut, I need to show that the left side's computation of the ciphertext matches the right side's, but I'm realizing the postcondition involves `Log.qs` which can change during the second adversary call, and I need to carefully handle how this universally quantified postcondition interacts with the bad event. I'm realizing this is the postcondition that emerges after the `call` instruction in the pRHL proof, where the pattern `(_: true, bad)` creates an obligation: either the inputs to the adversary's next call are equal across both games, or the bad event has already occurred. The frame postcondition captures this disjunction — if we can't guarantee equal inputs, we fall back on the bad event holding in the right game. I'm realizing the postcondition is establishing two possible outcomes: either the inputs to the adversary's second call are identical (guaranteeing equal results), or the bad event occurs where the adversary's output appears in the log. The universal quantification is EasyCrypt's way of expressing how the frame condition works with the `call` statement—it's saying this property must hold regardless of what happens after the call completes. When I test this with concrete values—say b{1}=true, b{2}=true, result_L=true, result_R=false—the equation breaks down to true=false, which fails. So for the postcondition to hold universally, I'd need both b{1}=b{2} and matching side effects, but that's only if these are outputs of the called procedure. Let me reconsider what the `call` statement with the upto pattern actually generates in EasyCrypt.

The postcondition with the universal quantifier is really EasyCrypt's abstraction over the procedure's results and side effects. What I actually need to show is that either the inputs to the next procedure call are equal on both sides, or the bad event holds. For the "good" case where the random value isn't in the log, I need both sides to compute the same result, which means the function inputs must match—requiring pk0=pk and r=Game1.r.

For the hash values, the left side gets h from the log oracle while the right side samples it fresh. If r hasn't been queried before, the log oracle returns a fresh sample too, so they can be coupled. But if r was already queried (the "bad" case), the log oracle returns the stored value instead of sampling fresh.

My strategy is to start by inlining the initialization code for both the log and oracle on both sides, then carefully handle the key generation to couple the key pairs correctly. I need to reconsider the approach—the oracle call blocks `wp` from progressing past that statement on the left side. Let me inline the oracle first to expose what happens after, then work through the weakest precondition reasoning with the conditional logic that emerges. I'm working through the logic of when `r` appears in the oracle's state: if it's fresh, we sample a new value directly, but if it was queried during the adversary's execution, it must be in the log since all queries route through there. So `r \in dom(LRO.m)` implies `r \in Log.qs` (assuming all queries go through Log, which they do in this setup since A uses Log(LRO)).

Actually wait, I need to be more careful. `LRO.m` maps from `rand` to `ptxt`. After `A(Log(LRO)).a1(pk)`, the domain of `LRO.m` contains exactly the set of queries made by A during a1, PLUS any that were in LRO.m before (which is empty since we just initialized). And `Log.qs` contains those same queries. So `r \in dom(LRO.m)` iff `r \in Log.qs` at this point.

But actually, `Log.qs` is a list, not a set. And the check `r \in LRO.m` checks the map domain.

They should be equivalent after initialization. But there's a subtlety—on the RHS, the code also calls `A(Log(LRO)).a1(pk)`, which modifies both `LRO.m` and `Log.qs`, so their final state depends on what the adversary does. Let me try a concrete approach using tactics to cut at key points. I'll start by trying to establish a good invariant after the adversary call and b sampling, maybe using `seq` to handle the initialization on both sides first. I'm considering a higher-level approach using `swap` to reorder the left-hand side statements to match the right-hand side structure, then applying `wp` and `rnd` to close out the proof. Alternatively, I could use `seq` to break the program into manageable pieces and handle each one separately. Let me start by inlining the init calls and using `wp` to handle the deterministic assignments, then tackle the divergent parts afterward.

Now I'm looking at what the code looks like on each side after inlining init—the left-hand side has a sequence of assignments and sampling steps leading to the ciphertext computation, while the right-hand side follows a similar structure but with some key differences in how the random values are sampled and combined. I think a better strategy is to inline both the init and the `LRO.o` call first, then work backwards from the end using `wp`, and finally handle the sampling steps. Continuing the inlined code...

Now I need to think through how the weakest precondition works here. The left side has deterministic assignments after the conditional block, while the right side has a conditional expression embedded directly in the final assignment. The key question is whether `wp` can reason through this conditional on the right before reaching the assignment itself.

Looking at the standard lazy oracle implementation in EasyCrypt, the sampling happens conditionally—the map gets updated with a fresh sample only if the input hasn't been queried before, then the procedure returns the stored value. I need to verify exactly how this oracle is structured to properly align the two programs.

After inlining, the conditional sampling creates a complication: the assignment to the map is guarded, which makes the proof trickier. Rather than trying to inline everything at once, I should break this down using the `seq` tactic to establish the invariant that shared state remains equal through the first phase of execution, up through the adversary's initial call. I need to consolidate the invariant to avoid redundancies—`Log.qs` is essentially `glob Log` since that's all the Log module contains, and `LRO.m` is part of `glob LRO`. So I'll use `={glob A, glob LRO, glob Log, pk, sk, m0, m1}` for the seq cut between statements 4 and 3. The local variable `kp` that gets destructured on the left side shouldn't affect the invariant since it's not part of the global state or the key variables I'm tracking.

Let me try submitting this tactic and see if EasyCrypt accepts it, though I might need to use `Log.qs` directly if it complains about the scope of `glob Log`. Actually, I'm reconsidering the whole approach—since this is the "up" layer move meant to undo over-lowering, maybe I should look for higher-level structure within the current goal rather than trying to work with the already-inlined code from the parent's `proc; inline BR93(LRO).keygen BR93(LRO).enc; call` sequence.

Looking at the goal state, I see the `A(Log(LRO)).a1(pk)` call appears on both sides, along with sampling statements that need coupling, with the key difference being the LRO.o call versus dptxt sampling. My strategy should be to use `seq` to isolate the A.a1 call, then apply `call` to handle it before tackling the remaining code. For the init calls, since `Log(LRO).init()` is identical on both sides, I can use `call` with an appropriate invariant rather than inlining.

Let me start by trying a `seq` tactic that advances past the init calls and establishes that the global state is equal at that point, then use `call` to handle the matching procedure calls. So after splitting at statement 4 on the LHS and statement 3 on the RHS, the second subgoal would have divergent code paths—the LHS continues with random bit selection and encryption operations while the RHS uses a different random value and plaintext sampling. I'd need to focus the "up" move on bridging this divergence, using the shared state of the adversary, log, and initial messages as the precondition.

For the second subgoal, my strategy is to couple the random bit selections first, then handle the extra assignments on the LHS, couple the random values, and finally reason about the oracle call versus direct sampling. The critical observation is that after the adversary runs, the log contains all queries it made, so if the new random value wasn't queried before, the oracle samples fresh randomness—which should align with the direct sampling on the RHS.

The key issue is determining when the bad event occurs: if the fresh random value collides with something already in the query log, the games diverge. Since the random value is sampled after the adversary's first phase, I need to show that when there's no collision with logged queries, both sides produce identical outputs, and the collision case is captured by the bad event. So the key insight is that the domain of `LRO.m` must equal the set of all logged queries—every query gets added to the log unconditionally, and each one triggers an operation that ensures the key exists in the map, so the two sets stay in perfect sync.

This means `r` is missing from the map exactly when it wasn't queried, and the bad event where `r` appears in the log is precisely when it's in the map's domain. The tricky part is that I need to make sure the local variable `r` and the module variable `Game1.r` are actually the same thing.

Let me start building the proof systematically, beginning with a `seq` cut to handle initialization and key generation separately. I should also think about what the `wp` tactic can handle here—it works well with deterministic assignments.

Looking at the weakest precondition from the end of both programs: on the left side, the final assignment is `c <- (f pk0 r, h +^ m)` with a procedure call `h <@ LRO.o(r)` before it, so `wp` stops there. On the right, the final assignment is similar but with `Game1.r` and a conditional, preceded by sampling statements. After applying `wp`, I'd absorb these final assignments and substitute the postcondition with the resulting expressions for `c`.

But the postcondition references `b{1}` and `b{2}` which are set earlier in the code, not in those final statements, so I need to work backwards further. Let me try a different strategy: first inline the oracle call on the left side, then use `wp` to handle deterministic assignments, `rnd` to couple the samplings, and conditional tactics to align the branches. Starting with inlining the oracle call on the left should expand its body and make the structure clearer for the subsequent proof steps. I need to be more careful about the exact tactic sequence. After inlining `LRO.o` on the left, I'll have the oracle body expanded inline, so I need to work through how the samplings and conditionals align between the two sides before committing to a tactic chain. I'm working through the coupling argument for the lazy oracle—when it samples unconditionally, I can align the samples on both sides of the game regardless of whether the key was already stored, which lets me show the outputs match in both cases.

Now I need to verify whether the standard EC ROM actually samples unconditionally by checking the clone definition in the source file. I'm considering a different strategy altogether—maybe I should use `swap` to rearrange the variable assignments that don't involve sampling or procedure calls, moving them toward the end before the final assignment. But I'm not convinced that actually helps. Let me try a cleaner approach instead: cut the proof after the A.a1 call, handle the initialization and key generation in the first part with inlining and tactics, then tackle the divergent section separately with inlining. I need to figure out which variables to include in the sequence cut invariant. `pk`, `sk`, `m0`, `m1` are present on both sides and get set by the prefix, so those should definitely be in there. The module globals `glob A`, `glob LRO`, and `Log.qs` should work too, though I'm wondering if `Log.qs` is already covered by `glob Log` or if I need to be more specific.

Let me go with `={glob A, glob LRO, glob Log, pk, sk, m0, m1}` as my invariant and start working through the proof. But first I need to check whether the prefix actually satisfies this invariant—let me trace through what the precondition gives me and see if I can establish the equality.

The precondition only has `={glob A, glob LRO}`, not `={glob Log}`, but that's okay because `init` sets `Log.qs` to `[]` on both sides anyway. After both sides run `Log(LRO).init()`, I get `Log.qs{1} = Log.qs{2} = []` and `LRO.m` resets to empty on both sides while `(glob A)` stays equal. Then the key generation happens differently on each side, so I need to track how `pk` and `sk` diverge.

For the proof strategy, I'm thinking I can use `seq` to cut at statement 4, then handle the deterministic init with `wp/auto`, apply `rnd` for the random key sampling, and finish with a `call` to `A.a1`. But I'm realizing the `seq 4 3` cut might create a mismatch in how the statements line up between the two sides. The key insight is that both sides are semantically equivalent since assigning to an intermediate variable versus destructuring directly produces the same result. For the proof, I need to establish that the oracles' state remains equal after the A.a1 call by showing the precondition ensures equal oracle state on both sides.

To handle the first subgoal, I'll use a call tactic with an invariant stating the oracles are synchronized, then inline the initialization procedures and work through the randomness and weakest precondition reasoning to complete the proof.

Actually, let me reconsider and try a more direct approach—inlining everything possible upfront with `inline*` to reduce the code to its essential form, then handling the remaining procedure calls with coupling tactics. Since A is an abstract declared module, `inline*` should inline all the concrete procedures while leaving A.a1 untouched, which gives me a cleaner starting point for the proof. I'm realizing that `A.a1` can't be inlined since A is abstract, but the `Log(LRO)` oracle passed to it might still be inlinable depending on how EasyCrypt handles oracle parameters. Let me try a more targeted approach by inlining just the init procedures first—that should give both sides matching initialization code at the start, then I can work through the rest of the proof step by step. Looking at the standard BR93 proof structure, I see that the parent already handled the initial setup and the call to A.a2, so I need to focus on the sequence before that—handling the initialization, the call to A.a1, and then closing out the remaining goals with the standard tactic sequence.

Let me try starting with `inline*` to expand everything, then use `sp` to handle the deterministic assignments from both sides, followed by a `call` tactic to establish the equivalence for A.a1 with the appropriate postcondition about the shared state, and finally work through the divergent parts.

Wait, I'm realizing the `call` tactic for A.a2 might actually leave me with two remaining subgoals—the body equivalence itself plus some side condition about the bad event or losslessness. Looking back at what the parent already proved with `exact A_a2_ll` and those `proc; call (LRO_o_ll _); auto` patterns, it seems like those were handling the auxiliary conditions around the call.

So the first goal in front of me is the body equivalence, and I should focus on that. Let me try inlining the initialization procedures to get a cleaner view of what I'm actually comparing, then see if I can push through with a higher-level tactic like `eager` or maybe break it down with `transitivity` to handle the random oracle equivalence more systematically.

Actually, I realize the precondition doesn't include `Log.qs`, but after the init calls set it to an empty list, both sides will have it equal. So I can use a sequence cut to establish that the globals match after initialization, which should simplify the body equivalence proof. so `={glob A, glob LRO, glob Log}` holds after init on both sides. I'll split this into two subgoals: first, proving the invariant is maintained through the initialization procedures using inline expansion and automation, then handling the remaining code with that invariant as the precondition. Let me try a larger cut instead of just one step to see if that makes the proof more tractable.

I'm setting up a sequence cut at positions 5 and 4 to split after the `b` sampling, which should separate the equivalent initialization phase from the divergent part where the oracle and random sampling differ. I need to verify that `b` is actually in scope as a local variable on both sides so it can appear in the invariant.

Now looking at what comes after the cut: the second subgoal shows the divergence clearly — the left side continues with the oracle query and ciphertext computation, while the right side switches to random sampling and plaintext operations. This split should make it easier to reason about the two branches separately.

For tackling this, I could expand the oracle definition inline first, then work backwards from the ciphertext assignment to absorb the hash computation, or I could push forward through the deterministic setup steps before handling the conditional and sampling operations.

Let me go with pushing forward through the setup—after handling the key and message assignments, I'll inline the oracle, then work backwards from the end to manage the remaining pieces. Once I do that, the left-side invariant should capture that the key and message are properly set up, and then I can deal with the random sampling and oracle call.

Inlining the oracle definition... Let me just try the straightforward approach and see what errors come up. I'll start with `sp 2.` to step through the first couple of deterministic assignments on the left side, though I need to check where statement 6 actually falls in the sequence.

Actually, looking at the program structure more carefully, the initial statements are procedure calls like `Log(LRO).init()`, which `sp` can't consume since it only handles deterministic code. So let me try a different tactic: `inline*.` to inline everything that's inlinable—the init procedures and the `LRO.o` call—which should leave just the abstract `A.a1` call to deal with separately. That way I can handle the remaining parts with standard tactics like `wp`, `call`, `rnd`, and `auto`.

After inlining, both sides would have the initialization statements from the procedures, the inlined body of `LRO.o`, and the `A.a1` call left as an abstract operation. This gives me a cleaner foundation to work from.

Actually, let me try a simpler approach first using `swap` to rearrange the left side to better align with the right. Looking at the two games side by side, I can see the structural mismatches: the left unpacks the key pair in two steps while the right does it in one, the left stores intermediate values like `pk0` and `m` that the right computes inline, and the left calls `LRO.o` to generate the ciphertext while the right samples directly from the plaintext distribution. The final assignment also differs in how it constructs the tuple. Alright, let me map out my approach: I'll inline the initialization procedures first, then use weakest precondition to absorb the deterministic assignments from the end. After that I can see what the goal looks like and decide how to proceed. I need to be careful about the LRO.o call on the left side since `wp` won't get past it, so I should inline that oracle call first to clear the way. Let me start by inlining both the init procedures and the oracle call together.

Now looking at the current goal state, I can see the previous approach already inlined the keygen and encryption procedures. What's left are the procedure calls: Log(LRO).init(), the adversary's a1 call, and the oracle call LRO.o(r) on the left side, with Log(LRO).init() and the a1 call on the right side.

The key insight is that I need to handle these calls in the right order for the proof. The init calls can be dealt with using the call tactic, and the a1 calls will need the adversary's invariant. The tricky part is the LRO.o call on the left side—I'll need to inline that and reason about what it does relative to the right side, which doesn't have that call at all.

Let me reconsider the structure: I could inline the initialization and the LRO.o call to eliminate them, leaving just the a1 call as the main thing to handle with the adversary's invariant. Then I can work backwards from the end using weakest precondition reasoning to absorb the remaining logic. code after A.a1 (since it's now deterministic + sampling after inlining LRO.o).

After inlining LRO.o, the code on the left side becomes deterministic up until the conditional, where `wp` would stop. So I need to handle the conditional separately, then use `rnd` to couple the samplings.

Actually, I think `call` in pRHL might be the right approach here. It matches the last call in both programs, and after inlining init and LRO.o, A.a1 would be the only module call remaining. Let me trace through what the left program looks like after those inlinings to see if `call` would work. Right, so after inlining init and the oracle, A.a1 becomes the only procedure call on both sides. To use the `call` tactic, I need to handle everything that comes after it first—the sampling and deterministic statements—by working backwards with `wp` and `rnd` to reduce the postcondition. But the conditional inside the inlined oracle blocks `wp` from passing through, so I need a different approach. Maybe I should try using `sp` to move forward through the deterministic assignments at the start instead, handling the left side's initial variable assignments before tackling the rest. I'm realizing that `sp` might actually simplify the precondition by handling those deterministic assignments, but I should verify whether it also processes samplings or if I need `rnd` for those. Rather than getting stuck on the theory, let me just try applying tactics sequentially and see what works—starting with swapping statement 6 on the left backward by 4 positions to reorder the key sampling. after statement 2. But wait, `swap` in pRHL needs the statement to not depend on earlier statements. `pk0 <- pk` depends on `pk` which is set at statement 3 (`(pk, sk) <- kp`). So I can't swap it before statement 3.

OK, I can swap it to after statement 3: `swap{1} 6 -2.` (from position 6 to position 4). That puts `pk0 <- pk` right after `(pk, sk) <- kp`. This is valid because pk0 doesn't affect anything between statements 4-5 (A.a1 and b sampling).

Wait, `pk0` is only used in the final statement `c <- (f pk0 r, h +^ m)`. And it doesn't affect A.a1 or b sampling. So swapping it should be fine.

But this doesn't fundamentally change the proof structure. Let me step back and focus on the core issue: I need to couple the oracle call `LRO.o(r)` on the left with the random sampling `h <$ dptxt` on the right, showing either they're equal or the bad event `Game1.r{2} \in Log.qs{2}` occurs.

The standard EasyCrypt approach is to inline the oracle, show that fresh sampling is equivalent when `r` isn't in the oracle's domain, and handle the case where it is. Let me start by inlining the oracle definition. This should inline all concrete procedures (init, LRO.o). If it causes problems, I'll try a more targeted approach.

Let me load the tool and try. Actually, let me think once more. If I use `inline*`, everything gets inlined. Then I have two versions to compare: the left side keeps the inlined LRO.o logic with conditional sampling and a lookup, while the right side simplifies by sampling directly and computing the result inline without the intermediate lookup. The key difference is how I handle the random value and the conditional—left preserves the game structure more explicitly, right collapses it. Now I need to use `call` to handle the remaining A.a1 invocation, which means working backwards from the end to reduce the postcondition to just what matters about the call's inputs and outputs. After `wp` absorbs those assignments, the postcondition still references `result_L`, `result_R`, and `qs_R`, which aren't actual program variables but rather represent outputs from the called procedure. The `wp` wouldn't eliminate `b{1}` and `b{2}` since they're set before the conditional and sampling statements where `wp` stops.

Looking at the universal quantification in the postcondition, if I instantiate `qs_R` as an empty list, then `Game1.r{2} \in qs_R` becomes false, which forces `(result_L = b{1}) = (result_R = b{2})` to hold for all possible values of `result_L` and `result_R`. This means `b{1}` and `b{2}` must be equal. I'm realizing the postcondition might be unsatisfiable when `qs_R` is empty—since `Game1.r{2} ∈ []` would be false, the entire disjunction fails unless the left side holds for all possible result values, which it can't. Let me reconsider the syntax: the `\/` operator is OR, so the postcondition is asserting that either the equality holds or the random value appears in the list, and this needs to be true for all combinations of results and lists. they're both booleans, so that's just `b{1} = b{2}`. But then with result_L = true and result_R = false, I get `b{1} = !b{2}`, which contradicts the first case. So I'd need both `b{1} = b{2}` and `b{1} ≠ b{2}` simultaneously—that's impossible.

This suggests the postcondition as I'm reading it is unsatisfiable. Let me look at the actual EasyCrypt goal output more carefully to see what I'm missing.

Ah, I think I've been misreading the operator precedence. The `=` might bind less tightly than `\/`, so this is actually saying that `result_L = b{1}` equals the entire disjunction `(result_R = b{2}) \/ (Game1.r{2} \in qs_R)`. That would make much more sense—both sides are booleans being compared for equality.

Now I'm working through what this postcondition actually requires. If I set `qs_R` to empty, I get that `result_L = b{1}` must equal `result_R = b{2}` for all possible results, which forces `b{1}` and `b{2}` to be identical. Then for any non-empty `qs_R`, the right side becomes true whenever the queried value appears in the list, which constrains how the results can differ. I'm realizing I need to reconsider how EasyCrypt's `call` tactic with the `upto` pattern structures its postcondition—specifically what the bound variables represent and how they relate to the original property before the call to A.a2. not after it. The `call` tactic transforms the goal so that the code after the call (the return) is handled, leaving the code before the call.

The frame condition for `call (_: true, bad)` where the overall post was `={res} \/ bad` says:

For the PRE of the call: either the call's inputs are equal (c{1} = c{2}) AND the bad event hasn't happened yet, OR the bad event has happened.

But the postcondition shown is different — it's universally quantified over result and qs_R.

Hmm, I think the universal quantification represents the fact that we need the property to hold for ANY possible execution of A.a2. Since A is adversarial, we can't predict its return value or queries. The `call (_: true, bad)` pattern says: "we don't need to couple A.a2's executions (hence `true` as the invariant); but we need to track the bad event."

So the frame condition is actually establishing what needs to be true before the call such that no matter what A.a2 returns or how it modifies the log, the overall postcondition still holds. The universal quantification captures this — we're saying the property must survive any possible behavior from the adversary. I'm realizing the postcondition requires either the inputs and state match across both sides (guaranteeing equal results), or the bad event occurs. But the universal quantification over `qs_R` is confusing—if it truly means "for all possible lists," then requiring `Game1.r` to be in every possible `qs_R` would be impossible. I suspect `qs_R` refers to the specific final state of `Log.qs` rather than an arbitrary list, which would make the quantifier meaningful in this context. I'm realizing the postcondition might be using `forall` in a way that's specific to EasyCrypt's representation—the result variables could actually be existentially quantified even if they appear universally quantified in the pretty-printer. Rather than getting stuck on the semantics, I should just try running tactics to see what works. Let me start with `inline*.` and work through the proof from there. now think this might be EasyCrypt's way of expressing: "for all possible continuations (represented by the universally quantified variables), the property holds." But in the `call (_: true, bad)` pattern, the `true` means "no coupling between the two calls" and `bad = (Game1.r \in Log.qs){2}`.

The `call` with upto in EasyCrypt generates goals of the form: the code before the call must establish conditions such that:
1. The call's precondition is met (here: `true`)
2. Either the bad event already holds, or the call inputs are equal

Since `true` is the call invariant (no coupling needed), the condition becomes:
- Either bad already holds before the call, OR
- The call inputs are equal AND b{1} = b{2}

The postcondition seems to be saying that after executing the code before the call, I need to establish that either the results match across both sides or the bad event can occur on the right side. The universally quantified variables here might represent the potential return values and side effects that the tactic introduces.

Rather than continuing to reason through the theory, I should just try running tactics and see what EasyCrypt accepts—the analysis isn't converging. My next step is to attempt `inline*.` I'm testing different parenthesizations of the postcondition to see which interpretation makes sense. If I parse it as `(result_L = b{1}) = ((result_R = b{2}) \/ (Game1.r{2} \in qs_R))`, then the left side equals true when result_L matches b{1}, and the right side is true when either result_R matches b{2} or the random value appears in the query set—this seems more plausible than requiring the random value to be in every possible query set. I'm hitting a dead end with this postcondition interpretation. Let me step back and try working through some tactics to see if things become clearer after simplification. Actually, I should reconsider how the `call` upto tactic works in EasyCrypt—specifically with the `call (_: true, bad)` pattern and upto-bad semantics. This generates a particular frame where the code before the call needs to establish either matching call arguments and the bad flag, or the bad condition itself. Let me think through what goal this actually produces when applied to the full body. The `call` tactic with the upto-bad pattern generates several goals: first it checks that both the left and right calls are lossless, then it verifies that the invariant is preserved when the bad event occurs and remains monotonic, and finally it confirms the precondition is established before the call. Looking at what the previous prover actually generated, it seems the framework handles these through specific tactics like proving losslessness directly and using contradiction for trivial cases.

Now I'm examining the remaining goals—the body equivalence before the call has a postcondition involving state variables and universally quantified results from the oracle call, which suggests it's framing the proof as: given any possible execution of the oracle, the overall result must hold. The pattern seems to shift when the condition changes from `bad` to `true`, which would alter how the goals are structured. then the bad event persists after the call since Log.qs only grows monotonically. But that doesn't help with the universal quantification over all possible qs_R values — I think the real insight is that the useful postcondition comes from establishing `b{1} = b{2}` and `c{1} = c{2}` upfront, which ensures the equality of results regardless of what the call returns.

Actually, wait — result_L and result_R are quantified independently, so they can differ. If I test specific cases like result_L = true and result_R = false, I get contradictory constraints on b{1} and b{2}. This means the postcondition can't hold for all possible result combinations.

But maybe the `=` operator in EasyCrypt works differently than I'm thinking. It could be logical equivalence rather than strict equality. Let me reconsider the postcondition with that interpretation — perhaps the binding is `(result_L = b{1}) = ((result_R = b{2}) ∨ (Game1.r{2} ∈ qs_R))`, which would change how the constraint propagates. I'm realizing the precedence matters here—if `=` actually has lower precedence than `\/` in EasyCrypt, then the expression parses differently, with the disjunction grouped first and the equality applied to the whole result. This would give me a different constraint that might actually be satisfiable depending on what values `result_L` and `result_R` can take.

But even with that parsing, when `qs_R` is empty the equation still forces a contradiction between `b{1}` and `b{2}`. I'm starting to suspect the `forall` quantifiers in the goal might not mean what I think—perhaps they're existentially quantified in the context of what the called procedure actually produces, rather than universally quantified over all possible values. Let me just try running tactics to see what happens.

Actually, I think the postcondition might be framed differently: it's not about the values themselves, but about what the code before the call must establish so the property holds for any continuation afterward. So if the overall goal is `={res} \/ bad` and `res` depends on the return value from `A.a2(c)`, then for this to work for all possible behaviors of `A.a2`, I need either the inputs to match perfectly so both sides return the same result, or I need to establish the `bad` flag.

Since `bad` is monotone—it only grows through the call—if it's already true before, it stays true after. So the frame condition becomes: either the call inputs and global state are identical, or the bad event already holds. That's really what the postcondition is checking underneath all the complexity.

I think the universally quantified version is the formal statement, but it should be equivalent to just checking that `b` and `c` are equal in both states, or that `Game1.r` is already in the log. Let me try proving this and see if the automation can handle the quantified goal once I establish those key facts.

Starting the proof now...

I'll try inlining the oracle call on the left side first with `inline{1} LRO.o.`, since that's the critical difference between the two programs. But I should be careful not to inline oracle calls in contexts where they don't make sense for an abstract module. Let me also inline the log initialization on both sides before diving in.

Loading the proof tool and committing tactics...

Good, I have the tool loaded and the workspace view confirmed. Let me analyze the goal and start the proof.

The current goal is a pRHL goal with 2 remaining goals. I need to prove equivalence (up to the bad event) between the LHS (BR93_CPA inlined) and RHS (Game1).

Let me think about my approach carefully.

The key difference is:
- LHS: `h <@ LRO.o(r)` (oracle call)
- RHS: `h <$ dptxt` (random sampling)

The postcondition is:


forall (result_L result_R : bool) (qs_R : rand list),
    (result_L = b{1}) = (result_R = b{2}) \/ (Game1.r{2} \in qs_R)

My approach: I'll inline the init and LRO.o calls, then work through the proof step by step. Let me try `inline*` first to inline everything at once, but I need to think carefully about what "up" means in this context.

Moving "up" means shifting to a higher abstraction level. I could use `seq` to cut at a high level and factor the proof, or try a Pr-level argument instead of directly proving the pRHL goal. Since I'm already inside a `byequiv`, Pr-level isn't available, so I'll focus on a clean `seq`-based decomposition. Let me cut after the `b <$ {0,1}` sampling on both sides to separate the initialization and keygen phases from the divergent part, then handle each subgoal separately.

For the second subgoal where the real work happens, I need to show the LHS and RHS are equivalent despite their different structures—the LHS uses the Log oracle while the RHS samples directly. I should verify how to properly reference Log's state in the proof.

Actually, I need to be careful about what the precondition gives me. It only establishes equality on `glob A` and `LRO.m` between the two sides, not on `glob Log`. But after initialization resets both Log.qs and LRO.m to empty, those globals become equal on both sides. So I should be able to prove the seq cut invariant `={glob A, glob LRO, glob Log, pk, sk, m0, m1, b}` for the first subgoal, though I need to verify this holds even after the A.a1 call modifies these globals.

Since both sides call A.a1 with identical inputs and oracle state, the outputs and resulting global state should match. Let me work backwards through the proof: first handle the random bit sampling, then the A.a1 call with the coupling assumption, then deal with the key generation difference, and finally the initialization. I'll try using a seq cut to establish the invariant at the midpoint.

I'm not entirely sure about variable scoping here, so let me just attempt this tactic and see what the proof state reveals.
