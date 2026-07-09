# Tree-0.1 · turn 1 · commit_tactic

<!-- session b8daceea-014c-4518-8491-4e89b1e76f77 · 2026-06-02T01:18:53.653Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; inline *; wp.`

---

Let me analyze the proof goal for `PIR_secure1`:

```
equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
```

The goal is:
```
pre = true
PIR.main ~ PIR.main 
post = PIR.s{1} = PIR.s{2}
```

This is a relational equivalence proof showing that the `PIR.s` variable has the same distribution regardless of the input `i`. Looking at `PIR.main`:

```
proc main (i:int) = {
    var r, r' : word;


```

The procedure initializes two lists and loops through indices, flipping a coin at each step. When the index matches the input `i`, the coin flip determines whether the index goes into `s` or `s'`, but when the index doesn't match, it goes into both lists regardless of the coin flip. After building these lists, it queries them and returns the XOR of the results.

For `PIR.s`: when `j = i`, `s` gets the index only if the coin flip is heads, but when `j ≠ i`, the index always goes into `s`. This means the distribution of `s` depends on which index was queried, which is exactly what we need to prove is indistinguishable between the two executions.

Actually, wait—I'm re-reading this more carefully. When `j = i`, `s` gets `j` only if `b` is true, and when `j ≠ i`, `s` gets `j` regardless of `b`. So `s` is built differently depending on `i`, which is the whole point. The proof for `s'` uses a similar approach but with a randomness argument to show the two executions are indistinguishable.

For `s`, I should follow the same tactic: inline everything, then use automation to handle the coupling argument.

Let me reconsider the proof strategy. I need to establish that `s` evolves identically in both branches by showing the loop invariant `={PIR.s, j}` holds throughout execution. the while loop, so I might need to manually guide it through the invariant that `s` and `j` stay equal on both sides. Let me try a simpler tactic first — just `proc; inline *; auto.` — and if that doesn't work, I'll add explicit loop handling with `wp` and guide the automation through each step.

Now let me try the seed tactic first: `proc; inline *; auto.`

Actually, wait. Let me think about this more carefully. The goal is an equiv statement. `proc` will enter the procedures. `inline *` will inline the `query` calls. Then we have a while loop and assignments.

`auto` alone probably won't handle the while loop — it typically needs an explicit invariant for while loops in pRHL. Let me try a more targeted approach.

Actually, let me just try the seed and see what happens. If it doesn't work, I'll adjust.


For equiv proofs with while loops in EasyCrypt, I typically need to establish the loop invariant explicitly using `wp` and then show that the invariant holds on both sides. Since `b` is sampled identically and `s` only depends on `b` and `j`, the identity coupling should work. Let me start by unfolding the procedures to see what I'm working with.

Looking at similar proofs, I can try committing `proc; inline *; wp.` followed by the while loop invariant. For PIR_secure1 where `s` evolves the same way on both sides, I might just need `auto` to close the loop body, or possibly `wp; rnd; skip => /> /#.` if there's more structure to handle. at the loop body, `auto` might struggle with the random sampling since pRHL requires explicit handling of `rnd` operations. I need to think through how the coupling works here — when `j = i`, the two branches diverge based on `b`, but when `j ≠ i`, both branches update `s` and `s'` identically, so the coupling should hold there.

Let me try a more direct approach: start with `proc; inline *; wp.` to handle the basic structure and weakest precondition, then tackle the while loop with the invariant `={PIR.s, j}` using a combination of tactics that can handle both the random sampling and the conditional logic.
