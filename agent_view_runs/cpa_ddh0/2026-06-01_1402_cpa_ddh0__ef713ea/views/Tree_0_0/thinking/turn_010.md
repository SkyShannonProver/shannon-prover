# Tree-0.0 · turn 10 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:10:16.657Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true).`

---

Let me read the full view to see the complete postcondition.

Now I see the full state. After `rnd.`, the boolean samplings have been coupled. The postcondition now uses `bL` (the coupled value) for both sides. The postcondition simplifies since `b{1} = b0{2} = bL`:

```
(forall (b0R : bool), b0R \in {0,1} => b0R = b0R) &&
forall (bL : bool),


bL \in {0,1} =>
bL = bL &&
((g ^ y{1}, pk{1} ^ y{1} * if bL then m1{1} else m0{1}) =
 (gy{2}, gz{2} * if bL then m1{2} else m0{2}) /\
 (glob A){1} = (glob A){2} /\ true) &&
forall (result_L result_R : bool) (A_L A_R : (glob A)),
  result_L = result_R /\ A_L = A_R /\ true =>
  (result_L = bL) = (result_R = bL)
```

The final part establishes that when the left and right results and global state are equal, the equality checks against the coupled bit also match.

The core constraint that remains is checking that the group element and public key computations produce identical values across both sides, along with the global state being preserved. Looking at the two program branches, the left side samples random values and derives the public key from them, while the right side appears to be doing something similar but the second program is incomplete.

Now I need to figure out how to handle the A.choose calls on both sides using the `call` tactic. My previous attempt with `call (_: ={glob A})` didn't work for A.guess, so I should try `call (_: true)` instead. Before committing to that, let me verify the structure: on the right side, after computing gx, gy, and gz, the A.choose call at position 6 is the final statement, and it's the same on the left where A.choose at position 4 is also last. This means I can apply the tactic directly to handle both A.choose invocations. The `call` tactic would match both A.choose invocations and require that their arguments are equal—meaning `g ^ sk0` on the left must equal `g ^ x` on the right, which forces `sk0 = x`. The deterministic assignments of gy and gz happen before A.choose is invoked, so they don't interfere with the call matching itself. I see—the `call` tactic only handles the function calls themselves, not the code before them. After applying `call`, the remaining programs would be everything that comes before the A.choose invocations, and the postcondition would need to capture the state at that point, including the values of gy and gz and how the arguments relate to each other. Let me just try `call (_: true).` and see what the proof state looks like.
