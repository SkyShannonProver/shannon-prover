# Tree-0.0 · turn 1 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:20:59.451Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc.`

---

Let me analyze the current proof state for `PIR_secure1`:

The goal is:
```
equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
```

So I need to prove that `PIR.s` is identically distributed in two runs of `PIR.main`, regardless of the input `i`.

Looking at the workspace view, I see several candidate moves:
1. `exact/PIR_s_uniform.` - This tries to use the `PIR_s_uniform` lemma directly


2. `exact/PIR_secure1.` - This would be circular (it's the lemma we're proving)
3. `exact/PIR_secure2.` - This proves `={PIR.s'}`, not `={PIR.s}`
4. `proc.` - Standard procedure opener

The strategy seed suggests `by byequiv lemma_name.` but that doesn't apply here since we're already proving an equiv statement. Looking at the already-proven `PIR_secure2` which establishes `={PIR.s'}`, I need to figure out how to relate that to proving `={PIR.s}` instead.

Examining the PIR.main procedure, I can see it maintains both `s` and `s'` lists throughout the loop, and the proof for `PIR_secure2` uses a while loop invariant with a randomized function to handle the branching logic. For `PIR_secure1`, I'll need a similar approach but focused on the `s` variable instead. I see the issue now—when `j = i`, the `b` flag controls whether `j` gets added to `s` or `s'`, but when `j ≠ i`, both `s` and `s'` get `j` added regardless of `b`. This asymmetry means `s` actually does depend on `i` through which branch executes, so I need a more careful coupling that accounts for this conditional behavior rather than treating it as independent. Verifying the loop invariant holds across all cases—whether `j` equals or differs from the loop index on either side, the conditional update ensures `s` only changes when `b` is true, so the equality is preserved.

Now I'm working through the proof tactics for the first case, starting with procedure inlining and weakest precondition reasoning to handle the loop. The key is figuring out how to manage the random sampling and subsequent conditional assignments—I need to either push the weakest precondition through the deterministic parts or use a randomness tactic with a transformation function that accounts for the conditional logic, similar to the pattern in the proven `PIR_secure2` case.

I'm checking whether `PIR_s_uniform` could directly apply here, but its signature doesn't quite match what I need since it's asserting something about the relationship between the two copies of `s` rather than establishing the equivalence I'm trying to prove.

Let me just work through the direct proof by first examining what the procedure body looks like after calling `proc.`, then building from there.

Let me start by probing `proc.` to see the procedure frontier, then build the proof step by step.

Actually, let me first think about the proof more carefully. The goal is:

```
equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
```

The precondition is `true` (not `={i}`), and we need `={PIR.s}`.

Looking at `PIR.main`:
```
proc main (i:int) = {
    var r, r' : word;


```

The procedure initializes variables and then loops through N iterations, where at each step it flips a random bit. When the index matches the input `i`, the bit determines whether the index goes into `s` or `s'`, but when it doesn't match, the index gets added to both lists regardless of the bit. After building these lists, it queries them and returns the XOR of the results.

Looking at how `s` gets populated: whether `j` equals `i` or not, `j` only gets added to `s` when `b` is true, so `s` is actually independent of `i`. To prove this in EasyCrypt, I'd use `proc; inline *; wp` to simplify, then apply the while loop invariant that `s` and `j` remain equal across both sides, followed by `wp; rnd; skip` to handle the random bit and skip the irrelevant branches. The `proc` tactic should handle the precondition fine, and after the simplification, `wp` will take care of the remaining tail with the query calls. Writing proof tactics...
