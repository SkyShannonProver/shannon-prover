# Tree-0.0 · turn 1 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:26:03.223Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_ : ={glob A, glob LRO, glob Log} ==> !(Game1.r \in Log.qs){2} => ={res}) : (Game1.r \in Log.qs) => //.`

---

Let me analyze the proof goal and the context carefully.

The goal is to prove:
```
Pr[BR93_CPA(A).main() @ &m : res] <=
Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]
```

This is a classic game-hopping lemma in the BR93 IND-CPA security proof. The lemma `pr_Game0_Game1` states that the probability of the adversary winning the CPA game is bounded by the probability of winning Game1 plus the probability of a "bad event" (that the random oracle query hits the challenge randomness).


Now I need to trace through the execution paths of both games to identify where they diverge. The BR93_CPA game initializes the log, generates a keypair, runs the adversary's first phase to get challenge messages, samples a bit, and then encrypts the chosen message. I should compare this step-by-step with Game1's execution to pinpoint the exact conditions under which the games produce different outcomes. The key insight is that `h` gets sampled fresh in `Game1` rather than queried from the random oracle like in `BR93_CPA`, so the games are indistinguishable unless the adversary happens to query the oracle at exactly `r` — that's the bad event. This is a standard "up to bad" argument where the probability difference comes down to whether that bad event occurs, and when it doesn't, both games produce identical distributions.

For the EasyCrypt proof, I'd use `byequiv` to establish equivalence up to the bad event, then apply the fundamental lemma to bound the original probability by the intermediate game plus the probability of the bad event. The strategy seems to be rewriting the left-hand side probability into an intermediate form that makes the equivalence clearer. a `<=` goal with the shape `Pr[G0:E] <= Pr[G1:E] + Pr[G1:F]`, the standard EasyCrypt approach might be to use the `fel` (failure event lemma) or the `byupto` tactic, or to manually apply the fundamental lemma.

Actually in EasyCrypt, there's a lemma pattern for "up to bad" reasoning. The typical approach is to use `byequiv` to establish that the two games are coupled and produce identical results unless a bad event occurs, which directly gives us the probability bound we need. Writing EasyCrypt proof... I'm working through how to structure the proof using `byequiv` to establish that the two games are equivalent up to the bad event, where the coupling maintains identical state for the relevant variables until the bad condition triggers, and the results match when the bad event doesn't occur. The key is figuring out the right intermediate form to rewrite the left-hand side probability to, which the seed suggests should be done with an equality step first.

Looking more carefully at the Game1 definition to understand exactly how it modifies the BR93_CPA game structure...

Game1 is essentially BR93_CPA(A) with three key modifications: it introduces a local variable `r`, inlines the key generation directly, and replaces the encryption step with a direct sampling of `r` from the random oracle's domain and `h` from the plaintext distribution rather than querying the oracle. The crucial insight is that when the adversary doesn't query `r` to the random oracle, the lazy oracle would return a fresh sample anyway, making the two games indistinguishable in that case. This sets up the foundation for an "up to bad" argument where I can bound the probability of the adversary querying `r`.

For the formal proof, I'm trying to establish an equivalence between the games using EasyCrypt's `byequiv` tactic with a failure event—specifically, the event that the adversary queries `r` to the random oracle. The tactic should prove that the probability difference between the two games is bounded by the probability of this failure event occurring. I'm still working through the exact syntax and whether `byequiv` directly supports this form or if I need to structure the proof differently. Let me think... Actually, in EasyCrypt, there's a specific tactic for "up to bad" reasoning. The goal `Pr[G0:E] <= Pr[G1:E] + Pr[G1:bad]` is directly the conclusion of the fundamental lemma.

I think the way to approach this in EasyCrypt might be using `byequiv` to show the two games are equivalent when bad doesn't happen, then applying probability manipulations to get the inequality. Or we could try the `fel` tactic if applicable.

Wait, but `pr_Game0_Game1` is the lemma we're proving, so I can't apply it as a cross-file reduction. The cross-file lemmas available are `pr_bad_Game1_Game2`, `pr_Game0_Game1`, and `pr_Game1_Game2`, but we're proving `pr_Game0_Game1` itself. Maybe the `have ->` is meant to transform the goal into a form that's easier to prove directly instead.

Actually, I think the more direct approach is using `byequiv` with the "up to bad" form, which directly gives us the bound we need by establishing equivalence between the games when the bad event doesn't occur. I'm not entirely sure about the exact EasyCrypt syntax for this, so let me just try a reasonable approach and see what happens. Since I can only use `commit_tactic`, `finish`, and a few other basic commands, I'll attempt the `byequiv` tactic with up-to-bad reasoning to prove the probability bound, then submit it and iterate based on feedback.

Good, I have the tool loaded and the current workspace view confirmed. The goal is:

```
Pr[BR93_CPA(A).main() @ &m : res] <=
Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]
```

This is the fundamental lemma / up-to-bad pattern. Let me think about the right EasyCrypt tactic.


The goal has the shape `Pr[G0:E] <= Pr[G1:E] + Pr[G1:bad]`, which is exactly what the `byequiv` tactic with a failure event annotation handles. I need to set up an equivalence proof where the post-condition relates the two games' results when the bad event doesn't occur, something like `!(Game1.r \in Log.qs){2} => ={res}`.

Actually, let me reconsider the exact form. The `byequiv` tactic with a bad event proves that the probability of event A in the first computation is bounded by the probability of A in the second plus the probability of the bad event in the second. For this to work, I need to show a coupling where either the bad event happens in the second game, or the results match between both games.

For my specific case, the bad event is `Game1.r \in Log.qs`, and I want to prove the results are equal when this doesn't happen. The precondition should establish that the relevant globals start in the same state across both games.

Setting up the tactic... I'm realizing that `Game1.r` is a module-level variable declared in the `with` block, so it exists as a global in the Game1 module. Since it only appears on the RHS, I don't need to include it in the precondition—it'll be initialized during execution. Let me reconsider the `byequiv` approach with the failure event annotation and think through whether this directly proves the `<=` goal in the form I'm trying to use. Proving:
```
Pr[G1 @ &m : E] <= Pr[G2 @ &m : E] + Pr[G2 @ &m : F]
```

The syntax is:
```
byequiv (_ : Pre ==> Post) : F => ...
```

where `Post` should imply `!F{2} => (E{1} <=> E{2})`.

So for our goal, I want:
```
byequiv (_ : ={glob A, glob LRO, glob Log} ==> !(Game1.r \in Log.qs){2} => ={res}) : (Game1.r \in Log.qs) => //.
```

I need to be careful about the `=> //.` part though. The `byequiv` tactic with a bad event generates multiple subgoals: the relational Hoare logic judgment, side conditions about precondition satisfiability, and possibly a bound on the bad event probability. Let me just try it and see what subgoals appear.

Actually, I should reconsider the strategy more carefully. The seed suggests using an opener like `have -> : Pr[<LHS>] = Pr[<intermediate>].` to rewrite the LHS to match a cross-file reduction lemma, but since I'm proving `pr_Game0_Game1` itself, I can't apply it as a lemma. Let me focus on what actually makes sense for this goal instead. Writing the byequiv tactic...
