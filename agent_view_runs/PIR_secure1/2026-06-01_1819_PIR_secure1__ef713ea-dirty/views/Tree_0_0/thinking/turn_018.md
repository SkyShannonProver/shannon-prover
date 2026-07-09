# Tree-0.0 · turn 18 · undo_to_checkpoint

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:31:03.362Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `{"checkpoint_id": "cp_2_dd6a7dcfb7c3afa8"}`

---

I see the checkpoint menu. I need to go back to before `proc.` (checkpoint cp_1) to restart completely with a different approach. Let me select cp_1 to undo everything back to the initial equiv state.

Wait, cp_1 is listed but I don't see it in the checkpoint_options... let me look again. The checkpoint_options show cp_5, cp_4 but the full list from the view shows cp_5, cp_4. Let me check if cp_1 is available.

Actually, looking at the checkpoint options more carefully:


- cp_5: auto. (step 5)
- cp_4: call (_: true). (step 4)

But in the view's structural_checkpoints, I also see these same two. The menu only shows checkpoints 4 and 5 because those are the most recent. But I need to go back further.

Actually wait, looking at the last view more carefully, the checkpoint_options in the `last_result` only show cp_5 and cp_4. But when I requested `undo_to_checkpoint {}`, the full list should show all checkpoints. Let me look...

The checkpoint_options in the result show: cp_5, cp_4, cp_3, cp_2, cp_1. Yes! cp_1 is there, so I can jump back to the very beginning.

I'm looking at the checkpoint details for cp_1, which would rewind me to before the `proc.` tactic was applied. Let me undo to that point and try a completely different approach instead of continuing down this path. Actually, I'm second-guessing whether going back to before `proc.` will really help—the core problem is the "programs in sync" mode constraint. Let me think through what strategy might actually work here.

Going back to cp_1 would leave me with the goal `equiv [PIR.main ~ PIR.main : true ==> ={PIR.s}]`. I could try strengthening the postcondition with `conseq` to require more, but that seems like it would just create additional proof obligations. What if I try a different tactic sequence like `proc; conseq (_: _ ==> ={PIR.s}); first last.` instead?

Actually, I should step back and look at the real bottleneck: after `proc.`, the programs are in sync mode, which blocks most tactics from working. The `sim.` tactic gets close but needs `={i}`, and my earlier `call (_: true)` attempt created an overly restrictive postcondition. Maybe I should undo further back to cp_2, before that first `call (_: true)`, and try a different approach to the call tactic itself.

The key insight is that `call (_: ={PIR.s}).` might work better than `call (_: true).` since it would preserve just the module state equality without forcing extra constraints. Though I need to be careful—`PIR.query` takes `s` as a local argument, not a module variable, so I need to verify that pRHL's call tactic handles module state preservation correctly in this context.

Let me backtrack to the checkpoint before any calls and try applying `call (_: ={PIR.s}).` sequentially for each of the two query calls, which should let the postcondition stay as just `={PIR.s}` without needing additional constraints.
