# Tree-0.0 · turn 11 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:10:42.128Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Good, `call (_: true)` was accepted for A.choose. Now let me read the full view to see the complete postcondition.

Now the remaining programs are:

Left:
1. sk0 <$ dt
2. y <$ dt
3. (pk, sk) <- (g ^ sk0, sk0)

Right:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)

Post:
```
(pk{1} = gx{2} /\ (glob A){1} = (glob A){2} /\ true) &&
forall (result_L result_R : ptxt * ptxt) (A_L A_R : (glob A)),


result_L = result_R /\ A_L = A_R /\ true =>
(forall (b0R : bool), b0R \in {0,1} => b0R = b0R) &&
forall (bL : bool),
  bL \in {0,1} =>
  bL = bL &&
  ((g ^ y{1}, pk{1} ^ y{1} * if bL then result_L.`2 else result_L.`1) =
   (gy{2}, gz{2} * if bL then result_R.`2 else result_R.`1)
```

Now I'm verifying that the left and right sides produce equivalent outputs when the results and global state match, checking that the computed values align correctly based on the boolean choice. Most of these constraints are trivially satisfied, so the key obligations are verifying that the public keys match—requiring `sk0{1} = x{2}`—and that the global state components are equal from the precondition, which then forces the random values to align as `y{1} = y{2}`. So everything reduces to `sk0{1} = x{2}` and `y{1} = y{2}`.

Now I need to handle the deterministic assignments on both sides—the public and secret key generation on the left versus the exponent computations on the right—along with the random samplings of `sk0`, `y`, and `x`. I'll use `wp.` to work through the deterministic parts, then apply `rnd.` for the random variables and `skip.` or `smt.` to discharge the remaining logical constraints.
