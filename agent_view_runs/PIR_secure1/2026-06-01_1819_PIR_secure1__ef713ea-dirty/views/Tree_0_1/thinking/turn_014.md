# Tree-0.1 · turn 14 · undo_to_checkpoint

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:28:25.529Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

The undo didn't actually undo `proc.` — it said the previous action was a read-only probe so there's nothing to undo from probes. The last committed tactic is still `proc.`. Let me use `undo_to_checkpoint` to see the checkpoint menu and undo `proc.`.

Actually wait, let me reconsider the approach. I'm still after `proc.` and the programs are in sync. The issue is:
1. `inline *` doesn't work (EasyCrypt rejects — nothing to inline in synced mode)
2. `wp` doesn't work (no progress — can't absorb past call sites)


3. `while` doesn't work (last instruction is a call, not a while)
4. `sim` works but leaves unprovable `i{1} = i{2}`

So in EasyCrypt, when programs are synchronized, relational tactics like `inline`, `wp`, and `while` don't apply to individual sides — they're treated as a unified program. Yet `sim` and `proc` both worked, which means some relational tactics do function here. I need to try something completely different.

Instead of the `proc; inline *; wp; while` chain, let me explore using `proc` followed by `sim` with a modifier to exclude the `i` variable from equality checking. The syntax should tell sim which variables are allowed to differ. I'm trying to recall the exact EasyCrypt syntax for this — it might be something like `sim /= /i.` or `sim /{i}.` where the `/` specifies which variables don't need to match.

Actually, let me step back and think about what `sim` is really doing here. After `proc`, the goal is to prove that the postcondition holds given the precondition, and `sim` assumes all variables are equal. Maybe I should use `conseq` to weaken the postcondition first, or reconsider what the residual goal actually is after `sim` runs. the postcondition, or maybe I should abandon the `proc.` approach entirely and try `byequiv` or another tactic at the module level instead. Let me first attempt using `conseq` to strengthen the postcondition so that `sim` can work without needing `i{1} = i{2}`, but I'm realizing that just restating the same goal won't help. Even committing to `sim` leaves me with an unprovable residual, so I need to think about whether there's a different entry point altogether.

Looking back at the undo attempt, it seems the manager didn't actually undo `proc.` — the response about the read-only probe suggests it interpreted my request as trying to undo the probe rather than the tactic itself, so the goal state is still in the post-`proc.` synchronized mode.
