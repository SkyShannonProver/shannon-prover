# Tree-0.0 · turn 1 · commit_tactic

<!-- session 661f19cc-73dc-4462-9d48-945b0b81b726 · 2026-06-02T01:18:30.018Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

Let me analyze the proof goal for `PIR_secure1`:

```
equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
```

The goal is:
```
pre = true
PIR.main ~ PIR.main 
post = PIR.s{1} = PIR.s{2}
```

This is a relational (equiv) judgment showing that `PIR.s` has the same distribution regardless of the input `i`. Looking at `PIR_secure2` which is already proven:


The proof strategy uses a while loop invariant to track that `PIR.s'` remains equal across both executions, then applies a randomness transformation that flips the random bit when the indices differ, ensuring the final state is indistinguishable regardless of which index was queried.

For `PIR_secure1`, I need to show the same equivalence holds for `PIR.s` by analyzing how the conditional logic distributes the index across the two lists — when `j = i`, only `s` gets updated based on `b`, but when `j ≠ i`, both lists receive the same update, so the symmetry of the construction guarantees they remain equal.

Writing proof code...

Actually, I need to be careful with the `rnd` tactic here — there's something subtle about how it handles the randomness in the coupling that I need to think through more carefully. Continuing with the proof strategy...

Since `s` only depends on `b` and `j` (not on `i`), identity coupling should preserve equality throughout. I'll start by entering the procedure and then work through the loop invariant, focusing on maintaining `s` equality while handling the cases where `s'` diverges based on `i`.
