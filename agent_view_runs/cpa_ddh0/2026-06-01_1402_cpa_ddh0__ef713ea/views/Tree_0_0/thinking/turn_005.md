# Tree-0.0 · turn 5 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:06:07.689Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

The swap worked. Now the programs are:

Left:
1. sk0 <$ dt
2. y <$ dt
3. (pk, sk) <- (g ^ sk0, sk0)
4. (m0, m1) <@ A.choose(pk)
5. b <$ {0,1}
6. pk0 <- pk
7. m <- if b then m1 else m0
8. c <- (g ^ y, pk0 ^ y * m)
9. b' <@ A.guess(c)


Right:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)
6. (m0, m1) <@ A.choose(gx)
7. b0 <$ {0,1}
8. b' <@ A.guess(gy, gz * if b0 then m1 else m0)
9. b <- b' = b0

Now I'll work backwards from the end using weakest precondition reasoning. The final step on the left is the adversary's guess, so I need to trace through what information flows into that.

On the right side, the last deterministic assignment `b <- b' = b0` needs to be pushed through the postcondition using weakest precondition, which transforms the equality check into one that accounts for the assignment. Then both sides converge to the same adversary guess call, and I can apply the weakest precondition rule for that oracle call.
