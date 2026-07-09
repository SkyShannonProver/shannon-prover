# Tree-0.0 · turn 10 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:26:55.073Z -->

**Intent:** `probe_tactic`  
**Payload:** `sim / {i} {i}.`

---

The `while` tactic failed with "invalid last instruction" — this means `while` in pRHL expects the while loop to be the LAST statement (the code should end with the while loop). But our code has `query` calls after the while loop. So we need to consume the tail first.

Route health says: "The while form is plausible, but the current frontier is not positioned at a loop tail."

So the issue is that the while loop is not at the end (there are statements 4 and 5 after it). In pRHL, `while` works backwards from the last instruction. We need to handle the tail first.


Since `wp` and `inline` don't work in the "programs in sync" mode, I'll try using `call` to handle the tail. The tail consists of two query calls with postcondition `={PIR.s}`, so I need a call spec that preserves this equality on the state.

Since `PIR.query` only reads the state without modifying it, I can use a spec like `call (_: ={PIR.s} ==> ={PIR.s})` — this says if the state is equal before the call, it remains equal after, which holds because the query doesn't change anything.

But I'm realizing the pRHL `call` tactic works differently than I initially thought. When I apply `call` with a precondition and postcondition, it replaces the current goal's postcondition with the call's precondition, then requires the call's postcondition to imply the original postcondition. So I need to structure the spec so that after the call succeeds, the equality `={PIR.s}` is preserved. I'm trying to figure out the exact EasyCrypt syntax for the `call` tactic — whether it's `call (_: ={PIR.s} ==> ={PIR.s}).` to specify both pre and postconditions, or if there's a simpler form like `call (_: ={PIR.s}).` that just sets an invariant. There seem to be multiple valid forms depending on whether I'm using an anonymous spec or referencing a named lemma. wp. indexed form in pRHL. Let me check `wp` tactic forms.

Actually wait — in the "programs in sync" mode, maybe the issue is that EasyCrypt doesn't print the programs as two-sided at all. Let me check what `call` form might work.

Let me try `call (_: true).` — using a simple invariant. This should work if `query` is a simple procedure that doesn't modify global state.

Actually, the fact that programs are "in sync" means EasyCrypt recognizes they are the same procedure pair. In this mode, maybe `wp` or `call` don't apply because EasyCrypt expects "two-sided" operations but there's nothing to separate.

Let me try a different approach entirely. Let me undo `proc.` and try `byequiv (_: true ==> ={PIR.s}) => //.` to get an explicit equiv judgment, then use a different proof structure.

Wait, `proc.` already exposed the equiv judgment. The issue is that in "programs in sync" mode, many standard pRHL tactics don't work. Let me try `nosimpl proc.` or some other variant — maybe I need to use `cfold` or other tactics to unsynchronize them.

Actually, let me try a different tactic entirely. I could undo `proc.` and instead try using `sim` with variable exclusion parameters to tell it not to couple the loop variable `i`. The idea is to prevent the synchronization that's causing the issue in the first place. I'm uncertain about the exact syntax, so let me test a few variations to see which one the `sim` tactic accepts.
