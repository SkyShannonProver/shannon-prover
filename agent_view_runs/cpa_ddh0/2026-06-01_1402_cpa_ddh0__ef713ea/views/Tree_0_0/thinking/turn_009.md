# Tree-0.0 · turn 9 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:09:38.763Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

The post is truncated. Let me read the full view.

Now I see the full state:

Left:
1. sk0 <$ dt
2. y <$ dt
3. (pk, sk) <- (g ^ sk0, sk0)
4. (m0, m1) <@ A.choose(pk)
5. b <$ {0,1}

Right:
1. x <$ dt
2. y <$ dt
3. gx <- g ^ x
4. gy <- g ^ y
5. gz <- g ^ (x * y)


6. (m0, m1) <@ A.choose(gx)
7. b0 <$ {0,1}

Now I'm setting up the postcondition that equates the outputs from both sides, checking that the adversary's global state remains consistent between them.

I need to couple the boolean samplings on each side—b on the left and b0 on the right—so they're equal. The `rnd` tactic should work here to couple these uniform samplings, but I need to be careful about statement positions since there are deterministic assignments after the samplings that might affect how the coupling works. I see that `wp` stopped at the sampling statements on both sides—`b <$ {0,1}` on the left and `b0 <$ {0,1}` on the right. Now I need to couple these two final samplings together using the identity bijection with `rnd.`
