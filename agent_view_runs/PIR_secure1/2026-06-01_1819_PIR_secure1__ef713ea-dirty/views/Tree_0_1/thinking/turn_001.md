# Tree-0.1 · turn 1 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:20:32.690Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc.`

---

Let me analyze the current proof state for `PIR_secure1`:

```
equiv PIR_secure1: PIR.main ~ PIR.main : true ==> ={PIR.s}.
```

The goal is:
```
pre = true
PIR.main ~ PIR.main 
post = PIR.s{1} = PIR.s{2}
```

This is a relational equivalence stating that `PIR.s` has the same distribution regardless of the input `i`. Looking at `PIR.main`, the variable `PIR.s` gets elements added to it:


When `j = i`, the coin flip `b` determines whether `i` goes into `s` on one side or `s'` on the other. When `j ≠ i`, both sides consistently add `j` to `s` whenever `b = true`. The asymmetry only appears at the secret index, where the two executions diverge based on the random bit. is added to `s` iff `b = true`, regardless of whether `j` equals `i`. So the value of `s` doesn't actually depend on `i` at all. For the proof, I'll use `proc; inline *; wp` with a while loop invariant that couples `s` and `j` identically, since the update to `s` is the same in both branches—it's just `j :: s` when `b = true`. Now let me check how `PIR_secure2` handles this...

Writing proof code... I'm realizing that `auto` alone won't handle the while loop after inlining, so I need a tactic that can reason about the loop structure. The `sim` tactic might not work either since the `s'` updates differ based on the `i` values, even though the `s` updates are identical on both sides. Let me try a combination like `proc; inline *; wp; while (={PIR.s, j}); auto` to handle the loop explicitly and then let automation finish the proof.
