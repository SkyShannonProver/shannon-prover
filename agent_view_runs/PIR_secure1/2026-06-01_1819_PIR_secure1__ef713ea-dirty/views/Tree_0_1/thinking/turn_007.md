# Tree-0.1 · turn 7 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:22:49.157Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (={PIR.s, j}).`

---

`sim.` was accepted! The goal after probe is:

```
forall &1 &2, true => i{1} = i{2}
```

So `sim.` reduced the proof to showing `i{1} = i{2}`. But our precondition is `true`, not `={i}`. The `sim` tactic tried to prove everything is equal but the `i` parameter differs between the two sides. So `sim` leaves behind the obligation that `i{1} = i{2}`, which we can't prove from `true`.

This means `sim` is the wrong approach for this postcondition — it tries to prove ALL variables are equal, but we only need `PIR.s` to be equal.


I need to reconsider the strategy. The real observation is that `PIR.s` gets updated the same way regardless of `i` — in both branches, element `j` is added to `PIR.s` exactly when `b = true`. So I should focus on coupling `PIR.s` and `j` while using identity coupling on `b`. Rather than relying on `inline *` and `wp` which don't work for synchronized programs, I'll need to manually construct a while loop invariant that tracks `={PIR.s, j}`.

Let me try using `sim` with a postcondition restriction to focus only on `PIR.s` equality, since the full state equality is too strong. I'm not sure of the exact syntax — it might be `sim (: ={PIR.s}).` or `sim (={PIR.s}).` — but the idea is to tell the tactic to ignore the other variables and just prove what matters. If that doesn't work, I could use `conseq` to weaken the postcondition first, though `sim` in pRHL typically expects synchronized programs with `={glob M}` style relations.

The real issue is that `sim` got stuck on `i`, so if I can exclude that from the equality requirement, the proof should go through. My plan is to set up a loop invariant that only tracks `PIR.s` and `j`, then handle the loop body with weakest precondition reasoning and randomness, finishing with `skip` and arithmetic simplification.

Let me try applying `while` directly to the synchronized programs after `proc.` since they share the same structure — that should let me establish the loop invariant without needing `i` in the equality.
