# Tree-0.0 · turn 6 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:24:22.780Z -->

**Intent:** `probe_tactic`  
**Payload:** `sp 2.`

---

`wp.` was rejected — it can't handle the procedure calls. And `inline *` was also rejected. Let me think differently.

The key issue is that after `proc.`, I need to handle the procedure tail (query calls). Let me try a different approach:

1. Use `conseq` to change the postcondition to something that only talks about `PIR.s`.
2. Or use `seq` to cut the proof at the while loop boundary.

Actually, I know! Let me try `conseq (_: _ ==> ={PIR.s}) => //.` — this uses `conseq` to weaken the postcondition and leave only the equiv proof. 

But wait, the postcondition is already `={PIR.s}`, so that won't help. Let me reconsider the structure: after `proc.`, I have the full procedure body with statements 1-5, where statements 4 and 5 are procedure calls. Standard pRHL tactics like `call` or `inline` should handle these, but `inline *` failed, so I need a different strategy.

Let me try using `call` to work backwards through the calls. In pRHL, tactics process from back to front like weakest precondition, so the first `call` would target the last statement. For the call `r' <@ PIR.query(PIR.s')`, since it doesn't modify `PIR.s`, the postcondition `={PIR.s}` should carry through—I just need to specify the call precondition and postcondition properly.

Actually, I'm realizing `call` in pRHL introduces a new equivalence judgment for the called procedure itself. Since both sides invoke `PIR.query`, I need to provide an equivalence spec for that call. But wait, the overall postcondition is `={PIR.s}` and the call doesn't touch that, so maybe I should switch tactics—use `sp` to consume the initialization from the front, then handle the loop with `while`, and work through the remaining statements from there.

Let me reconsider the approach. EasyCrypt is displaying the programs in a single column since they're synchronized, and `wp` failed because of the procedure calls while `inline *` didn't work either. I should try a more targeted inline like `inline{1} PIR.query` or `inline{2} PIR.query`, or maybe just use `sp 2` to consume the two initialization statements, then apply `while` for the loop invariant, and handle the rest with `call` or `sim`.

Actually, the cleaner approach might be to undo `proc` and use `sim` with a loop invariant directly—something like `sim (: ={PIR.s, j})` to tell the simulator to maintain that invariant through the loop. sim` might not work without `={i}`, so I need to think about whether strengthening the postcondition helps or if I should try a completely different tactic strategy altogether.

Let me reconsider the structure: I need to handle the initialization statements first, then work with the while loop and the subsequent query calls. If I use `sp` to step through the initialization, I can isolate the loop, and then apply a while invariant that tracks the relevant state equality. The key insight is that the while loop creates separate subgoals for the loop body and the tail, so I need to ensure the postcondition for the tail (the query calls) is achievable with just `={PIR.s}`. I'm trying a different tactic with `conseq` to establish an intermediate invariant, but I need to be careful about how the precondition and postcondition weakening works—I can't just assume `true` implies a more specific state relationship without justification.

Let me just try `sp 2` to skip past the initialization statements and get to the while loop, then apply the while tactic directly.
