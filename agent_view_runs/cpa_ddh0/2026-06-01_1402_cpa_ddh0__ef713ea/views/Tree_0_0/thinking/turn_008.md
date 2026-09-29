# Tree-0.0 · turn 8 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:09:12.024Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

`call (_: true).` was accepted. Let me read the full view to see the new goal and postcondition.

Now I can see the postcondition clearly. After `call (_: true).`, the post is:

```
(c{1} = (gy{2}, gz{2} * if b0{2} then m1{2} else m0{2}) /\
 (glob A){1} = (glob A){2} /\ true) &&
forall (result_L result_R : bool) (A_L A_R : (glob A)),
  result_L = result_R /\ A_L = A_R /\ true =>
  (result_L = b{1}) = (result_R = b0{2})
```

The `&&` is a conjunction in EasyCrypt (the "and-also" operator). So there are two parts:
1. `c{1} = (gy{2}, gz{2} * if b0{2} then m1{2} else m0{2}) /\ (glob A){1} = (glob A){2} /\ true`
2. `forall (result_L result_R : bool) (A_L A_R : (glob A)), result_L = result_R /\ A_L = A_R /\ true => (result_L = b{1}) = (result_R = b0{2})`

The second part is a universal quantification stating that whenever the results and global state match between the two executions, the boolean results must also match.

Looking at the postcondition requirements, I need:
- c{1} to equal the ciphertext pair from the right side
- The global state to be identical on both sides
- b{1} and b0{2} to be equal

Now examining what the remaining programs need to establish... I'm working through the weakest precondition calculation, folding the deterministic assignments upward on both sides. On the left, I have the final assignment for `c` along with the conditional assignment for `m` and the binding for `pk0`, while the right side ends with a random sampling. I need to be careful here since `wp` processes deterministic steps but the right side has a sampling operation that breaks the pattern. I need to substitute `pk = g ^ sk0` into the postcondition. This gives me `pk{1} ^ y{1} = g ^ (sk0{1} * y{1})`, and comparing both sides of the equation, I see that the first components match when `y{1} = y{2}`, which means the sampling of `y` on both sides must be identical.

For the second components to match, I need `sk0{1} = x{2}`, `b{1} = b0{2}`, and the message pairs to be equal. Now let me apply the weakest precondition tactic and see what constraints emerge.
