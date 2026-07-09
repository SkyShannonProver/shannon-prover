# Tree-0.1 · turn 6 · undo_last_step

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:41:00.714Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

OK, so `call (_: ={glob Log, glob LRO}).` was accepted. It generated 3 goals (was 2 before, now 3). The first goal is the oracle preservation:

```
equiv[Log(LRO).o ~ Log(LRO).o : 
  ={arg, Log.qs, LRO.m} ==> 
  ={res, Log.qs, LRO.m}]
```

This is provable (same oracle, same inputs). But the issue is that the precondition for the `call` requires `={glob Log, glob LRO}` BEFORE the `a2` call, which is NOT true after the encryption step (since `LRO.m` differs).


This approach won't work — the oracle invariant is provable, but I can't satisfy the precondition from the encryption step. Let me backtrack and try the "upto bad" approach instead. I need to figure out why the earlier attempt with `eq_except` failed. The syntax `call (_: inv, bad).` might not be correct, or maybe `eq_except` isn't in scope from the `FMap` import.

Actually, looking at this more carefully, the issue might be that EasyCrypt doesn't support that particular `call` syntax for "upto bad" reasoning. I could try using a `seq` tactic to split the proof at the boundary before the `a2` call, or explore other tactics like `upto` or `eager`. Let me step back and reconsider the entire proof strategy from scratch.

Instead of trying to force a `byequiv` with a disjunctive postcondition `={res} \/ bad`, I could decompose this differently: first establish an upper bound on the probability using `byequiv` to show `Pr[...] <= Pr[... : res \/ bad]`, then apply probability union bounds to separate the terms. Or I could try proving directly that the games are identical when `bad` doesn't occur, which would give me the inequality I need.

But there's a problem—`bad'` doesn't exist in G0, so that approach won't work cleanly. Let me step back and try splitting the code explicitly with `seq` at the `a2` boundary, then handle the oracle call separately using `sim` if I can make the oracle states match, or find another technique. The key insight would be ensuring that the invariant either implies the global states are equal or that `bad` has occurred, which would let me case-split the proof—though EasyCrypt might not support that directly.

Actually, I'm realizing there's a cleaner way to think about this. After encryption, either the random value wasn't in the oracle's map before (in which case the map gets extended), or it was already there and logged, meaning `bad` is already true. In the second case, the postcondition trivially holds since it's a disjunction with `bad`. For the first case, I need the "upto bad" reasoning to apply to the `a2` call. Instead of splitting on `bad` explicitly, maybe I should construct a stronger combined invariant that covers both the encryption step and the `a2` call together.

Let me undo my recent tactics and try a different strategy entirely. I'll undo that `call` tactic since it created unsolvable goals—the equality on the oracle's map won't hold. Then I'll try splitting the probability using `mu_split` on whether `Game1.r \in Log.qs` before attempting the `byequiv` argument.

But wait, I'm running into the same issue: `Game1.r` is a module variable that doesn't exist in G0, so I can't split on it there. What if I introduce an intermediate game that's equivalent to G0 but also tracks `r`? Game1 already does this, so maybe I should work with that structure instead. The core inequality `Pr[G0 : res] <= Pr[G1 : res] + Pr[G1 : bad]` is really about bounding the difference between the two games by the probability of the bad event in G1.

I should apply the fundamental lemma of game playing here—if G0 and G1 behave identically when the bad event doesn't occur, then the difference in their probabilities is bounded by the probability of bad in one of the games. EasyCrypt likely has this as a library lemma, something like an "upto_bad" lemma that formalizes this relationship.

Defining the lemma... I'm trying a different approach using a `have` statement to decompose the goal into two parts: first establishing an equivalence between the original game and a disjunctive event, then applying the probability union lemma to split that into a sum. The union lemma in EasyCrypt gives me the sum of probabilities minus their intersection, so I need to account for that overlap term.

The real challenge is that `byequiv` generates a pRHL judgment where the postcondition becomes an implication rather than an equality—specifically `res{1} => (res{2} \/ bad{2})`—and I need to handle how this implication interacts with the `a2` call in the proof.

The standard `call` tactic for abstract adversaries requires the oracle invariant to maintain `={res}` across each call, but with the "upto bad" reasoning, this constraint becomes problematic. I think I need to explore whether EasyCrypt supports a variant of the `call` tactic that can work with two separate invariants: one for the good case where bad hasn't occurred, and another for when bad has been set.

Trying different syntax...

Actually, I just realized my earlier `call (_: ={glob Log, glob LRO}).` was accepted by EasyCrypt and did change the proof state—the real problem is that the remaining code needs those equalities to hold before the `a2` call, but they won't be provable after the encryption step. Let me think about whether I can manually handle the postcondition mismatch instead.

Maybe I should try `proc*` instead of `call` to see if it handles the oracle replacement differently, or completely restart with a different strategy using `eager` or `rnd` tactics to transform the oracle rather than relying on "upto bad" reasoning.

Actually, I'm realizing I might be overcomplicating this—what if I change the postcondition for the equivalence to use implication instead of biconditional, expressing that `res{1}` implies `res{2} \/ bad{2}`, which would be weaker than requiring equality and give me more flexibility in the proof?

For the adversary call, the "upto bad" reasoning should work: when bad hasn't occurred, the oracles return identical results so the adversary behaves the same way, and if the first game's output matches the initial value, the second game's output must too or bad triggers. But I keep running into the same wall—the oracles still need to agree when bad hasn't happened, which is the fundamental constraint I'm trying to work around. Let me step back and think about whether EasyCrypt has a tactic or pattern specifically designed for this kind of "upto bad" reasoning with abstract adversary calls.

Actually, maybe I should try the `eager` tactic to transform the oracle into eager sampling—pre-computing all values upfront so queries become simple lookups independent of the adversary's history. That might sidestep the dependency issue entirely, though I'm not certain how to apply it here. Let me try backing up and approaching this more fundamentally.

What if I use `byequiv` with an "upto bad" annotation to handle the case where the adversary queries a key it's already seen? The syntax would specify that the games are equivalent up to the bad event occurring, which should generate the standard proof obligations for that scenario.

Trying a different call specification... Trying different syntax variations to isolate the issue—it could be a syntax error with the comma form, missing predicates in scope, or the `call` tactic not supporting this structure. Let me undo and test simpler approaches to narrow down what's causing the rejection.
