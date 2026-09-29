# Tree-0.0 · turn 3 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:31:54.465Z -->

**Intent:** `commit_tactic`  
**Payload:** `have h : Pr[BR93_CPA(A).main() @ &m : res] <= Pr[Game1.main() @ &m : res \/ Game1.r \in Log.qs].`

---

The `byequiv` with failure event is still being rejected. Let me think about what's going wrong. The error details are not shown, which makes this harder. Let me try a completely different approach.

Maybe the issue is that EasyCrypt's `byequiv` with the `: (bad_event)` syntax for up-to-bad reasoning has a different form than what I'm using. Or maybe this version of EasyCrypt doesn't support the `byequiv ... : bad` syntax at all.

Let me try alternative approaches:

1. Try `byequiv` without the bad event, just to check if the basic `byequiv` works


2. Try `fel` (failure event lemma)
3. Try a manual decomposition using `have` and `Pr` lemmas

I'm testing a simple `byequiv` that tries to prove equality of results given matching initial state, though this would establish equality rather than the inequality I actually need. The real problem might be that `byequiv` is designed for equality goals, not for the `<=` ordering I'm working with here.

Looking at the EasyCrypt documentation, `byequiv` can handle both standard equality goals and upto-bad forms where you prove an inequality by accounting for a bad event. For the inequality case, I need to structure the postcondition to explicitly track when the bad event occurs and ensure it's synchronized across both games.

Let me try using `mem` syntax instead of the `\in` operator, which might be more compatible with how EasyCrypt parses the bad event condition in the upto-bad form.

Actually, I'm realizing the real constraint here—for `byequiv` to work on a `<=` goal with the upto-bad pattern, both probability terms on the right side need to reference the same program and memory state, with the bad event being a specific predicate on that shared program.

Let me try stripping this down to the absolute minimum and see what error EasyCrypt actually returns, since that might give me a clue about what's going wrong with the tactic application.

I'm thinking about using a different approach entirely—instead of fighting with `byequiv`, I could use a `have` statement to manually apply the probability bound reasoning. The core idea is that when two games agree on the negation of some event, I can bound the probability of one game's outcome by the sum of the other game's outcome probability plus the event probability. Let me try setting up a transitivity chain where I first establish an upper bound using the union bound principle.

The challenge is figuring out the right EasyCrypt lemmas and syntax—`Pr[...]` notation is really `mu` under the hood, and I need to find the correct union bound lemma, whether that's `mu_or` or something similar. Let me explore using `rewrite` to apply the union bound directly to the probability expression.

Actually, `byequiv` might not work for this `<=` form at all, so let me test whether the tactic can even handle inequality goals or if I need a different approach entirely. I'm looking at how similar proofs are structured in EasyCrypt examples—the pattern typically uses `byequiv` with a postcondition that allows either equal results or a bad event occurring. Let me try reformulating this with `={res} \/ (Game1.r \in Log.qs){2}` as the postcondition, which captures that either the results match or the bad event happens in both games.

But I'm realizing the logical distinction matters here: `={res} \/ bad{2}` actually means `res{1} = res{2} \/ bad{2}`, which is weaker than what I need. For the `<=` direction, I need `res{1} => (res{2} \/ bad{2})` instead—if the first game's result is true, then either the second game's result is true or the bad event occurred. These aren't equivalent, so I need to be more careful about which postcondition captures the right relationship.

For a `<=` goal, `byequiv` might only need one direction rather than both, so the EasyCrypt upto-bad facility should handle this. Let me try formulating it with the `={res} \/ bad{2}` postcondition and see if EasyCrypt accepts it, though I'm starting to suspect `byequiv` might have trouble matching the `<=` goal pattern directly. only work on `=` goals for probabilities. For `<=` goals, we might need a different entry point.

Let me check if there's a specific tactic or lemma for "upto bad" reasoning in EasyCrypt.

In EasyCrypt's standard library, there should be lemmas like probability bound utilities. I think the approach here is to split the goal into two parts: first, establish that the original game's probability is bounded by a disjunctive event, then apply the union bound to separate that into two independent probability terms. For the first step, I can use `byequiv` to prove the inequality between probability statements, and for the second, I'll use the union bound lemma to decompose the disjunction into a sum of probabilities. I'm working through the syntax for EasyCrypt tactics and realizing I need to be careful with JSON escaping—the `\/` operator requires proper escaping to render correctly. Let me step back and think about what actually works: `byequiv` handles equality goals cleanly, but for `<=` goals with bad event annotations, I might need to use probability manipulation lemmas or a manual transitivity approach instead of trying to force `byequiv` to work here. as intermediate steps. For step 1, I need to prove the probability inequality using `byequiv`, which can handle `<=` goals when the postcondition is structured as an implication. For step 2, I'll apply the union bound to decompose the probability, likely using `Pr_mu_or` or similar lemmas to split the disjunction.

I'm considering whether to use `byequiv` directly on the `<=` goal or build up intermediate results with `have` statements and transitivity. Since I can't see EasyCrypt's error messages, I should start with a simple approach—maybe just trying `byequiv` bare to see what subgoals it generates, then work from there.

Let me look back at the actual proof statement to understand the structure better. I need to figure out what standard EasyCrypt lemmas handle probability bounds like this, and whether there's a pattern in similar proofs I can follow. Maybe the issue is that `Game1` is a local module, which could require special handling in `byequiv`, or perhaps the `with` syntax creates an implicit module structure that the tactic doesn't recognize properly. Let me try a different approach using `eager` tactics for game idealization, or possibly `byphoare` to reason about the probability bounds directly. games are different. The games only agree when the bad event doesn't happen.

Hmm, let me think about what's fundamentally going on.

Actually, I just had an idea. Maybe I should look at how EasyCrypt's `with` module syntax works. The `Game1 = BR93_CPA(A) with { ... }` syntax creates a module that shares code with `BR93_CPA(A)` but with certain procedures overridden. The `byequiv` tactic might need to know which procedure to compare.

But in `byequiv`, the procedure is automatically inferred from the `Pr[M.proc(...) @ &m : ...]` goal.

Let me try a completely different approach. Let me try to use `eager` based reasoning, or inline the modules manually.

Actually, let me try the most basic approach: `proc`.

In some EasyCrypt developments, for goals involving `Pr[M.proc() @ &m : E] <= Pr[N.proc() @ &m : F]`, you can use the `proc` tactic (not `byequiv`) which directly creates a pRHL judgment. But I'm not sure.

Actually no, for probability goals, `byequiv` is the standard entry point. `proc` is for inside the pRHL proof.

Let me try one more thing. Maybe the postcondition format is wrong. In EasyCrypt, for the upto-bad `byequiv`, the postcondition and bad event must together match the goal exactly. Let me check if the bad event needs to match `Game1.r \in Log.qs` exactly as written in the goal.

Actually, I wonder if the issue is that the bad event references both `Game1` and `Log` modules, but maybe EasyCrypt requires it to reference only one side, or perhaps needs explicit side annotations like `Game1.r{2} \in Log.qs{2}`. Since the bad event in `byequiv` is automatically interpreted as the right side, `Game1.r` might not exist on that side in the original `BR93_CPA(A)` module.

I think the core issue is that `BR93_CPA(A)` doesn't have a variable `r`, so the bad event can't be expressed on the left side of the equivalence. I need to modify the left game to also track `r`, or use a different bad event that's expressible on both sides. I'm working through the probability chain using inclusion-exclusion: the probability of `Game1` producing `res` or the bad event is at most the sum of their individual probabilities, and this upper bound relates back to the original game through a `byequiv` argument showing that when the bad event doesn't occur, both games agree on the result.

Let me try using EasyCrypt's probability rewriting tactics to decompose the probability expression by splitting on whether `Game1.r` is in the log, which would separate the cases I need to bound. I'm trying a completely different approach by looking at what EasyCrypt's standard library offers for probability reasoning. There are useful lemmas like `mu_sub` for monotonicity, `mu_or_le` for disjunctions, and `mu_split` for partitioning events, which should let me decompose the probability inequality I'm trying to prove.

The key insight is that I can rewrite the goal as showing `Pr[G0:res] <= Pr[G1:res \/ bad]` through a coupling argument, then apply the union bound to get `Pr[G1:res] + Pr[G1:bad]`. This gives me a two-step proof strategy using `byequiv` for the coupling and a probability lemma for the union bound, which I can chain together with transitivity. I'm realizing that `byequiv` with an implication postcondition should handle the `<=` case between two `Pr` terms, so I could introduce an intermediate bound as a `have` statement and prove it that way, then apply the union bound—though this is getting complex, so let me explore whether there's a simpler approach or if the syntax issue is just a matter of using a different keyword in this EasyCrypt version.

Testing `byequiv upto`...

Actually, let me step back and check if `byequiv` even works with `<=` goals in this version of EasyCrypt. The real issue might be that the tactic simply doesn't support inequality goals at all.

Let me try a manual decomposition instead. I'll break down the probability inequality by establishing that the sum of probabilities in G1 bounds the probability in G0, then work through the logical relationships between the game outcomes. I'm trying to figure out which lemma handles the union bound correctly—`Pr[A ∨ B] ≤ Pr[A] + Pr[B]`—and realizing that either `Pr_mu_or_le` or the inclusion-exclusion principle would work since the intersection term is non-negative. Let me step back and try a simpler tactic approach using the seed's suggestion of introducing an intermediate game with `have ->` to rewrite the left-hand side, though I'm not sure if I can define a local game module from tactics. Maybe I should try the `eager` tactic instead to connect the two games directly. I'm stepping back to try the most straightforward tactics first. Let me attempt `byequiv` to see if that makes progress on this inequality goal, and if not, I'll use the probability lemma that relates the difference between games to the bad event probability.

Since I can't examine other proof traces directly, I'm looking at the ROM theory file to find relevant lemmas for this game-hopping pattern. The stability and losslessness properties of the logging oracle should give me the tools I need.

Let me try a more direct approach by manually constructing the proof step with a `have` statement that bounds the original game's probability against a modified version where the bad event occurs.

Writing tactic code... I'm trying different tactics to see which one works—starting with a simple `byequiv` call with a basic postcondition to test whether it can handle `<=` goals at all, then moving to intermediate steps or probability splitting if needed.

Now I'm thinking about using `mu_split` to decompose the probability on the right side, which would split `Pr[G1:res]` into cases where the bad event occurs and where it doesn't, giving me a sum of three terms that I can then bound individually. The standard approach in EasyCrypt for proving this kind of bound is using `byequiv` with a bad event, so I should try that tactic with the proper syntax. I'm thinking the issue might be with how I'm specifying the module names or the event condition itself—let me experiment with explicit module references and different formatting for the bad event specification to see what the proof checker accepts. I'm wondering if maybe the `<=>` operator is what's needed here instead of `={res}`, since that might not work in this context. Let me think about whether the bad event declaration needs to match the goal's `Game1.r \in Log.qs` exactly, accounting for potential normalization issues with the `\in` operator. Rather than keep guessing at syntax variations, I should systematically try the simplest approach first—just `byequiv => //.` and see if EasyCrypt accepts it.

Actually, I need to step back and understand how EasyCrypt internally represents this goal. The inequality is between a single `Pr` term on the left and a sum of two `Pr` terms on the right, so `byequiv` needs to recognize this as a "upto bad" pattern. Looking at how the tactic is defined in EasyCrypt's source, it matches a specific pattern structure for these kinds of goals.

Let me try some alternative tactic names that might work in this version—`upto` with the failure event, or `pr_upto`, since different EasyCrypt versions use different naming conventions. I should check the tactic reference to see what's actually available.

Actually, I realize the right postcondition for a `<=` goal should express that if the event holds on the left, then either it holds on the right or the bad event occurred—something like `res{1} => res{2} \/ bad{2}`. Let me try formulating the `byequiv` call with this implication-based postcondition instead.

The core issue is that `byequiv` expects a two-term probability inequality, but our goal has three terms: `Pr[G0:res] <= Pr[G1:res] + Pr[G1:bad]`. I need to first collapse this into a two-term form by showing that `Pr[G1:res] + Pr[G1:bad] >= Pr[G1:res \/ bad]`, then apply `byequiv` to the simplified goal. I'm working through the probability reasoning for the CPA game reduction, trying to establish that the adversary's success probability in the BR93_CPA game is bounded by the probability of either winning in Game1 or the random value appearing in the query log. I'm considering using intermediate `have` statements with `byequiv` to build up the chain of inequalities, since direct application of transitivity with probability expressions might be syntactically tricky in the proof assistant. I need to be careful with the escape sequences when writing this tactic in JSON format—`\in` for membership and `\/` for disjunction both need to be properly escaped so they appear correctly in the EasyCrypt syntax.
