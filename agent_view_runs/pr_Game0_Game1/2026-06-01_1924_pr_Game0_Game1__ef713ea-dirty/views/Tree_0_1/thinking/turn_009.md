# Tree-0.1 · turn 9 · undo_last_step

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:42:42.094Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

The `call (_: true, (Game1.r \in Log.qs){2}).` was accepted! So the comma syntax for "upto bad" calls works. It generated 6 goals (was 2, now 6). The current goal is:

```
forall (ARO <: POracle{-A}), islossless ARO.o => islossless A(ARO).a2
```

This is the adversary losslessness goal, which I can prove with `A_a2_ll`.

Let me see all the goals. But first, let me understand: the `call (_: true, bad)` was accepted but the invariant `true` is way too weak — it doesn't maintain any coupling between the two sides. 

The real invariant needs to preserve `={res}` across oracle calls when bad hasn't occurred. My earlier attempt with `eq_except` and `pred1` probably failed because those predicates weren't in scope. Let me try a different approach with a properly constructed invariant that maintains the coupling without relying on those potentially inaccessible functions. I'm trying to figure out if `eq_except` is actually available in scope, since `FMap` was imported at the top but `ROM` might be shadowing or reexporting conflicting map operations from `SmtMap`.

Let me try rewriting the invariant without `eq_except` and use a direct forall quantifier instead, specifying that the maps are equal everywhere except at `Game1.r{2}`.
