# Tree-0.0 · turn 12 · undo_to_checkpoint

<!-- session 420ddf0e-a769-49f3-83cb-e3b3c3d9112b · 2026-06-03T16:10:34.924Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

This is the core sampling bound. But I notice a problem: to bound the `a_ = G1.g_ ^ G1.u'` coordinate by `qD/(order-1)`, I need `u' ↦ g_^u'` to be injective, which requires `G1.w <> zero` (so `g_` is a generator). My cut predicate `size G3.cilog <= PKE_.qD` dropped that fact. I need to redo the seq-13 cut with a stronger invariant. Let me view the checkpoint menu.
