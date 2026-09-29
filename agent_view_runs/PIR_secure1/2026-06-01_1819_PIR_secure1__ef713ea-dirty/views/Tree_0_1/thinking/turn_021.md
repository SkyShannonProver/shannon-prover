# Tree-0.1 · turn 21 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:32:33.338Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &1 &2 a; byequiv => //.`

---

The probe of `move=> &1 &2 a; byequiv => //.` was accepted! The resulting goal is:

```
&1: {arg: {i: int}}
&2: {arg: {i: int}}
a: int list
------------------------------------------------------------------------
pre = arg{2} = arg{2} /\ arg{1} = arg{1}

    PIR.main ~ PIR.main

post = PIR.s{1} = a <=> PIR.s{2} = a
```

This is interesting! Now:
- The precondition is `arg{2} = arg{2} /\ arg{1} = arg{1}` which simplifies to `true` (trivially true)


- The postcondition `PIR.s{1} = a <=> PIR.s{2} = a` is weaker than `PIR.s{1} = PIR.s{2}` since it only requires equivalence with respect to a specific value `a` rather than full equality. After applying `proc.`, the programs might still be in sync, but I need to see what the postcondition becomes.

After `proc; inline *; wp.`, the postcondition shifts to `(PIR.s{1} = a) = (PIR.s{2} = a)` as a boolean equality, which changes the structure of what I'm trying to prove. The key insight is that `PIR.s{1} = a <=> PIR.s{2} = a` can be established by proving `PIR.s{1} = PIR.s{2}`, so I'm facing the same fundamental synchronization challenge. Using `sim` might help here since it would try to establish variable equality, which would imply the postcondition, though it would still leave the unprovable `i{1} = i{2}` residual.

Looking at how `PIR_s_uniform` handles this with `bypr` and probability goals, I'm thinking that after `proc.` with the new postcondition, I could use an invariant like `={PIR.s, j}` through the while loop, and then the postcondition would follow directly since `PIR.s{1} = PIR.s{2}` implies the boolean equality.

The problem is that `proc` synchronizes the programs, but then `inline *` fails. However, in this context where the precondition has different arguments `arg{1}` and `arg{2}`, maybe `proc` won't actually synchronize them. Let me try committing `move=> &1 &2 a; byequiv => //.` and then test `proc; inline *; wp.` to see if it works now.
