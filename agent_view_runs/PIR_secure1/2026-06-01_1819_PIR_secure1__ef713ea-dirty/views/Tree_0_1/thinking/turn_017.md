# Tree-0.1 · turn 17 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:30:13.886Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; sim /i.`

---

`bypr (PIR.s{1}) (PIR.s{2}).` was accepted! It produces 2 subgoals:

Goal 1 (trivial):
```
forall &1 &2 (a : int list),
  PIR.s{1} = a => PIR.s{2} = a => PIR.s{1} = PIR.s{2}
```

Goal 2 (the main obligation):
This should be: for all &1 &2 a, true => Pr[PIR.main(i{1}) @ &1 : PIR.s = a] = Pr[PIR.main(i{2}) @ &2 : PIR.s = a].


The first goal closes immediately with `smt()` since both equalities give us the transitivity we need. For the second goal, I need to show the probabilities are equal for any value `a`. Since `Pr_PIR_s` is still admitted, I'll need to either use `byphoare` or establish the probability equality directly for each side. I'm reconsidering the approach—maybe I can prove `PIR_secure1` more directly by showing that `PIR.main` produces identical distributions for `PIR.s` regardless of the input `i`. After `proc.`, I could try using `sp` to step through the initial assignments and then `conseq` to handle the suffix, or experiment with different `inline` targets to get around the synchronization issue that blocked `wp` earlier.

Let me try using `sim / i` to exclude the variable `i` from the equality requirement, though I need to verify the correct EasyCrypt syntax for this—it might be `sim /={i}` or `sim /{i}`.

Actually, I should just go with the `bypr` approach since that was already accepted. Or I could try `proc` followed by `conseq` to adjust the postcondition, but that still requires proving `={i}` which I don't have. Let me commit to `bypr` and handle the remaining subgoals.
