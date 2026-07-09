# Tree-0.0 · turn 28 · commit_tactic

<!-- session b9b6df1c-2d45-4f29-b7d5-cce4da2b9fcc · 2026-06-03T18:50:18.704Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r.`

---

Let me read the `rnd` probe preview to see the reduced goal.

`rnd` (bare) charges the *entire* product budget to one sample — the resulting `mu dt (…) <= product` post is unprovable (a single coordinate only gives `qD/order`). So bare `rnd` is a dead end; I need to drop `A.choose` and decompose per-coordinate. The choose-drop requires the `size <= qD` seq the guard blocked. Now that the goal is reshaped (post is a membership, invariant certified), let me retry committing that seq directly.
