# Tree-0.1 · turn 20 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:31:54.442Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> &1 &2 a; byequiv => //.`

---

First subgoal closed. Now the second (and remaining) subgoal is:

```
forall &1 &2 (a : int list),
  Pr[PIR.main(arg{1}) @ &1 : PIR.s = a] =
  Pr[PIR.main(arg{2}) @ &2 : PIR.s = a]
```

I need to show that the probability of `PIR.s = a` is the same regardless of the argument `arg` (which is `i`) and the memory `&m`.

My approach: use `byequiv` to convert this back to an equiv, but this time with a DIFFERENT precondition that makes the programs NOT synchronized. Specifically:


I'll introduce the universally quantified variables and then apply `byequiv` with a postcondition that equates the final states of `PIR.s` across both executions, relying on the fact that the global state of PIR is identical in both branches. The precondition `={glob PIR}` ensures the initial states match, but since `PIR.s` gets reset to `[]` in both branches anyway, the real constraint comes from maintaining the loop invariant with `={PIR.s, j}` throughout execution—the challenge is that this invariant needs to hold despite the apparent independence of the initial values.

Let me try a different tactic with the proof script...
