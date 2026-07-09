# Tree-0.1 · turn 3 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:04:39.370Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

The view is truncated. Let me read the full workspace view to see the complete goal.

Now I can see the full pRHL goal:

LHS (CPA):
```
(pk, sk) <@ ElGamal.kg()
(m0, m1) <@ A.choose(pk)
b <$ {0,1}
c <@ ElGamal.enc(pk, if b then m1 else m0)
b' <@ A.guess(c)
```

RHS (DDH0):
```
x <$ dt
y <$ dt
b <@ DDHAdv(A).guess(g ^ x, g ^ y, g ^ (x * y))


```

The success condition is checking if b' equals b. The RHS is more streamlined since it samples x and y, then delegates the rest to the DDH adversary. I need to flatten both sides by inlining all the operations to get a direct comparison.
