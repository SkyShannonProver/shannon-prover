# Tree-0.0 · turn 17 · undo_to_checkpoint

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:30:33.915Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

Now I have 1 remaining goal with just the init + while loop (no more query calls!). The frontier shows:
- first instruction: `while (j < Top.N) {`
- The while is at the end now (after consuming the query calls)!

Let me read the full goal to see the postcondition, which should now include the frame from both calls.

Let me read the full view to see the postcondition.

Actually, looking at the truncated preview, I can see the goal has:
- pre = true
- Statements 1-3 (j init, s/s' init, while loop)


- Postcondition: involves ={PIR.s} and ={PIR.s'} in some complex way

Let me pull up the full goal from the workspace to understand what the postcondition is actually asserting.

Now I can see the full goal:

```
pre = true

(1) j <- 0
(2) (PIR.s, PIR.s') <- ([], [])
(3) while loop

post =
  (PIR.s{1} = PIR.s{2} /\ true) &&
  forall (result_L result_R : word),
    result_L = result_R /\ true =>
    (PIR.s'{1} = PIR.s'{2} /\ true) &&


```

The postcondition requires `={PIR.s}` and `={PIR.s'}`, with the `forall result...` parts coming from the `call (_: true)` handling. Since the while loop is the last statement, I should be able to use `while I` here. I need an invariant that implies the postcondition when the loop guard becomes false.

The tricky part is proving `={PIR.s'}` from just `true` — but `s'` actually depends on `i` since different branches add different values to it depending on whether `j = i` or `j != i`. Looking at the full postcondition structure, it's nested with multiple `forall` quantifiers and conjunctions that all need to hold. The condition boils down to needing both `PIR.s{1} = PIR.s{2}` and `PIR.s'{1} = PIR.s'{2}` after the loop, but the identity coupling can't preserve the second one since `s'` gets different values depending on whether `j` equals `i` on each side—if the indices diverge, the left and right executions will add different things to `s'`. The postcondition requires both `={PIR.s}` and `={PIR.s'}` to hold, but the `call (_: true)` invocations didn't frame those equalities across the call boundaries. The frame obligation ledger flagged this exact issue — the weak `true` invariant failed to carry the equality facts forward, so now I'm stuck needing to prove something the calls never established.

I should try using `call (_: ={PIR.s}).` instead to explicitly preserve that equality across the calls. Since `PIR.query` only reads its argument and doesn't modify the module variable `PIR.s`, this frame fact should hold, which would simplify the postcondition requirement. I need to reconsider what postcondition EasyCrypt generates when I use `call (_: true)` for the second query call. The issue is that `PIR.query` doesn't modify global state, so `PIR.s` should remain unchanged, but I'm getting an unexpected postcondition involving `={PIR.s'}` that doesn't seem right. Let me trace through more carefully what the call semantics are doing here. invariant `true` means: the procedure preserves `true` (trivially). But EasyCrypt's `call` tactic in pRHL generates:
- The call spec obligation: `equiv [f ~ f : true ==> true]`
- A residual goal: the remaining code, with postcondition that combines the original post with the call's pre

The way EasyCrypt combines them might produce the complex postcondition I see.

Hmm, I think the issue is that `call (_: true)` doesn't carry `={PIR.s}` through the call. A better approach would be to use `call (_: ={PIR.s}).` or even better, use `conseq` to simplify the postcondition.

Actually wait. Let me reconsider the whole approach. Instead of handling the calls one by one, maybe I should undo back to the initial `proc.` state and try `conseq` to set a cleaner postcondition like `={PIR.s}`, then attempt `sim` with specific exclusions or manually work through the while loop. The complex postcondition I'm seeing actually might still be provable since it requires both `={PIR.s}` and `={PIR.s'}` to hold, but it's getting unwieldy. I need to reconsider how EasyCrypt actually handles the `call` tactic in pRHL—specifically, when I use `call (_: ={PIR.s})`, the residual postcondition gets computed by substituting the call invariant into the original postcondition, which means I'm left requiring `={PIR.s'}` at the end, not just `={PIR.s}`. So this doesn't actually solve the problem; I still need a coupling that proves `={PIR.s'}` from the weaker precondition.

Let me try a different tactic entirely: using `sim` with an explicit loop invariant to handle both the initialization and the while loop together, specifying that `PIR.s` and `j` remain equal throughout.

Actually, I'm realizing the real problem—the current postcondition demands both `={PIR.s}` and `={PIR.s'}`, but I can't establish the primed version with identity coupling. That impossible postcondition came from using `call (_: true)`, so I need to backtrack before that first call and try a completely different strategy.

Let me check the checkpoint list to find where I was before diving into the call work, then consider whether I can use consequence to relax the postcondition down to just what I actually need. I realize the `while` tactic failed before because it wasn't the last instruction, but now that I've handled both function calls, the while loop should be positioned correctly as the final instruction. Let me attempt applying `while` with the invariant `={PIR.s, j}` and check whether this invariant can actually satisfy the postcondition, which involves nested quantifiers over result values and state equality conditions. I need to check what checkpoints are available by using the undo menu to see their current IDs and find the right point to backtrack to before attempting the call with the equality assumption instead.
