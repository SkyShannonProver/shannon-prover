# Tree-0.1 · turn 22 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:54:27.248Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; inline BR93(LRO).keygen BR93(LRO).enc.`

---

Good, I'm back to the state after the `byequiv` (step 1 replayed), before `proc`. The goal is:

```
pre = ={glob A, LRO.m}

    BR93_CPA(A).main ~ Game1.main 

post = res{1} = res{2} \/ (Game1.r{2} \in Log.qs{2})
```

Now I need a different approach. Let me think carefully about how to prove this.

The key issue is the `a2` call where the oracle states differ. I couldn't make `call (_: non_trivial_inv, bad)` work.
 
Let me try using `proc` followed by `conseq` to strengthen the postcondition with an intermediate invariant that tracks when the two games' states align and when the adversary's output appears in the log, then derive the original postcondition from there.

But I'm still stuck on the `call` for `a2` when the oracle states differ between games. What if I abandon `call` entirely and use `eager` instead? The `eager` tactic can reorder oracle evaluations to show that the lazy evaluation during encryption can be deferred until after the adversary queries, or skipped entirely if they never query that value.

Looking at the existing `OW_OWr` proof in the file, it uses `byequiv` with a simple reflexivity argument, which suggests I might be overcomplicating this. Maybe I should try a similar direct equivalence approach rather than fighting with the module structure mismatch. I'm trying a different approach with `proc` and `conseq` to strengthen the postcondition, but I realize this won't help because the `call` tactic with a non-trivial invariant was already rejected. Let me reconsider what's happening—`call (_: true, bad)` works fine, but adding any equality constraint like `={Log.qs}` causes it to fail, which suggests the issue isn't about what the invariant is, but how EasyCrypt's `call` tactic handles the "upto bad" syntax when there's a non-trivial precondition.

When I use `call (_: inv, bad)`, EasyCrypt generates several proof obligations: losslessness of the oracle under the invariant, equivalence preservation in the good case, and bad monotonicity. With `inv = true` this simplifies nicely, but with a non-trivial invariant the losslessness requirement becomes much harder to satisfy.

The real issue is that `call` generates PHOARE goals (unilateral) for bad monotonicity, which means the invariant must be expressible as a unilateral predicate. But `={Log.qs}` is relational—it compares state across two execution paths—so it can't appear in a unilateral `phoare` context. That's why the proof is failing: the invariant I'm trying to use is fundamentally incompatible with the proof obligations the tactic generates. I'm realizing the precondition in that goal was actually `!true`, which evaluates to false, making the entire equivalence vacuously true. Let me trace back through what those generated goals actually were to understand the pattern better. post = true

This is the oracle preservation in the BAD case: when bad has already happened AND !inv. With `inv = true`, `!inv = !true = false`, making the precondition false (vacuously true).

So the goals from `call (_: true, bad)` are:
1. A_a2_ll — adversary losslessness
2. Oracle equiv with `!inv /\ ={arg} /\ bad ==> post` — with `inv = true`, this is `false ==> true` (vacuous)
3. phoare for losslessness — `true ==> true` (trivial)
4. Maybe another phoare for the other side
5. Maybe more goals
6. The prefix pRHL goal

With `inv = ={Log.qs}`, I'm realizing that the negation of this relational equality might be causing issues. The negation `!={Log.qs}` isn't standard EasyCrypt syntax—it should be written as `Log.qs{1} <> Log.qs{2}` instead. When EasyCrypt generates goals from `call (_: inv, bad)`, it might not be able to properly construct `!={Log.qs}` as part of the oracle goal, which could be why the tactic is failing.

If that's the problem, I should rewrite the invariant explicitly so its negation is well-formed. Instead of the shorthand notation, I'll express it as a conjunction of equalities, which negates cleanly to a disjunction of inequalities that EasyCrypt can handle properly. Let me try rewriting the `proc` with this approach.

Actually, I'm realizing I need to step back—I'm already at the equivalence goal level before even applying `proc`. Let me reconsider whether I actually need both `proc` and `inline` before the `call`, or if I can structure this more directly. The key issue is that `LRO.m{1} = LRO.m{2}` isn't quite right as an invariant since the maps diverge after encryption happens.

I should try using an explicit forall quantifier to express that the maps are equal except at the specific key, rather than relying on the `eq_except` shorthand. But I'm pretty sure I already attempted this exact formulation before and it was rejected by the system.

Looking back at my previous attempts, even the simpler `={Log.qs}` invariant alone was rejected, while `true` went through. The pattern seems to be that `true` works because it's a 0-ary predicate with no program state references, whereas anything that directly references module variables like `Log.qs{1}` and `Log.qs{2}` gets rejected. Maybe EasyCrypt's `call` tactic has stricter requirements about what kind of invariants it accepts—perhaps they can't reference specific module variables or need to be expressed as pure relational predicates without module paths.

Let me test whether using explicit equality without the shorthand notation makes a difference.
