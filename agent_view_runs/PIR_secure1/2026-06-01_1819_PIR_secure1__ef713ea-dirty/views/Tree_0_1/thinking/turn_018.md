# Tree-0.1 · turn 18 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:31:09.628Z -->

**Intent:** `commit_tactic`  
**Payload:** `bypr (PIR.s{1}) (PIR.s{2}).`

---

"unknown variable or constant: `i'" — the `sim /i` syntax doesn't recognize `i` as a variable because `i` is a procedure argument, not a program variable in the current scope (before proc).

Let me go with the `bypr` approach. Let me commit it and handle the two subgoals.

Actually, before committing `bypr`, let me think about whether I can handle the second subgoal. The `bypr` will give me:

Goal 1: `forall &1 &2 (a : int list), PIR.s{1} = a => PIR.s{2} = a => PIR.s{1} = PIR.s{2}`


This is trivially solved with `smt()` or a simple move and implication elimination.

Goal 2: `forall &1 &2 (a : int list), true => Pr[PIR.main(i{1}) @ &1 : PIR.s = a] = Pr[PIR.main(i{2}) @ &2 : PIR.s = a]`
Now I'm realizing that after `bypr`, I'm working in a logical goal rather than a pRHL goal, so `i{1}` and `i{2}` don't make sense in this context — `i` is a procedure parameter, not something that can be instantiated with different values.

Looking at the actual goal structure more carefully, the first goal should be establishing that if `PIR.s` equals some value `a` in both memories, then they're equal to each other. The second goal is about probability equivalence — showing that the probability of `PIR.s` equaling `a` is the same across both executions, where the arguments to `PIR.main` are whatever was passed in the respective memories.

To prove the probability equivalence, I could use `byphoare` to compute the probability on each side separately, or I could try `byequiv` to convert back to an equivalence relation. But there's a circular problem here — using `byequiv` would require proving the same equivalence we're already trying to establish, which doesn't help. The key is that I'm now working in a probability context rather than relational Hoare logic, so I need a different approach that doesn't just loop back to the original problem. Unless... I use a different coupling. In the bypr goal, I need to show:
```
Pr[PIR.main(i1) @ &m1 : PIR.s = a] = Pr[PIR.main(i2) @ &m2 : PIR.s = a]
```

I can prove each side independently using `byphoare`. For each side:
```
Pr[PIR.main(i0) @ &m : PIR.s = a] = <some value independent of i0>
```

The probability that `PIR.s = a` depends only on which subset `a` represents, since each `b` is an independent coin flip and `PIR.s` collects exactly those indices where `b = true`. But computing this probability exactly is what `Pr_PIR_s` does, and that's admitted.

Let me try a different approach using `byequiv` inside the `bypr` goal to relate the two sides directly. I'd set up an equivalence proof that shows the two programs produce the same `PIR.s` value when they start with the same global state, then work through the loop with synchronized randomness. The key insight is that even though the two sides have different arguments, the equivalence should still hold because `PIR.s` doesn't actually depend on which input was chosen. Writing the equiv proof...

I'm realizing the `byequiv` approach gets messy with the precondition derivation, so let me pivot to using `bypr` instead and work through the subgoals as they come up. Actually, I'm wondering if I can skip `proc` entirely and use `sim` at the module level to project onto just the `PIR.s` component—though I'm not confident that syntax exists in EasyCrypt. Let me just commit to `bypr` and see what happens.

The first subgoal should be straightforward, but I'll need to figure out the second one. Before I do that, let me try one more thing: what if I use `proc` followed by `call` to handle the concrete procedure calls at the end? Or maybe `wp` with explicit indices could absorb the two call statements from both sides since the programs are synchronized.

Actually, I'm realizing that `wp` in pRHL only works on assignments and skip statements, not procedure calls. Since the `query` calls are procedure calls, `wp` won't make progress on them. So I need to inline those calls first after using `proc`, then work with the resulting assignments.

Let me try using `inline` with side-specific annotations like `inline{1}` and `inline{2}` to inline the query calls on each side separately, though I'm not sure if that syntax applies to synchronized programs.

I think my best bet is to commit the `bypr` approach and then use `byequiv` to set up a new equivalence proof where the programs don't have to stay synchronized, which might give me more flexibility in handling the second subgoal.
