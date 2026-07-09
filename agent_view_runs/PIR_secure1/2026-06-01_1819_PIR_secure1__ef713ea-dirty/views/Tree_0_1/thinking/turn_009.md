# Tree-0.1 · turn 9 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:24:55.408Z -->

**Intent:** `probe_tactic`  
**Payload:** `seq 3: (={PIR.s}).`

---

OK, `inline PIR.query.` was also rejected. Let me try a different approach entirely. Let me undo the `proc.` commit and try `proc; inline *; wp.` as a single compound tactic. Maybe the issue is that `inline *` and `wp` don't work independently after `proc.` but the compound form works differently.

Actually wait, I already tried `proc; inline *; wp.` as a probe before committing `proc.` and it was rejected too.

Let me think about this from scratch. The key issue is:


1. After `proc.`, the programs are "in sync" 
2. `inline *`, `wp`, `inline PIR.query` all fail/make no progress
3. `sim.` works but requires `i{1} = i{2}` which we can't prove
4. `while` fails because the while loop isn't the last instruction

Maybe I should try `call (_: true).` to handle the last call to `query`. In pRHL, `call` processes from the end (bottom-up), handling the last procedure call on each side. Or perhaps `call (_: ={PIR.s}).` would work better to process that final call with the right postcondition.

The key insight is that `query` doesn't modify `PIR.s`, so establishing the invariant `={PIR.s}` through the call should be straightforward. I'm trying different `call` tactic forms to see which syntax works in EasyCrypt for this concrete module procedure.

But wait—I'm realizing that `call` is meant for abstract procedures, not concrete ones. For concrete procedures, I'd normally inline them and use weakest precondition reasoning. Yet `inline *` was accepted but made no progress, while `inline PIR.query` was rejected entirely. This suggests EasyCrypt may have already inlined the query calls when it reported the programs were in sync, but the goal still displays the unevaluated `PIR.query` call, which is puzzling.

Let me reconsider what "programs are in sync" actually means—it's probably just a display optimization showing identical code in a single column, not a signal that inlining has already happened. The tactics should still work. But the manager is warning that `inline *.` would be auto-reverted if it detects no progress, so I can't force it through. Instead, I'll try using `seq` to split the program at a specific position and prove the subgoals separately.
