# Tree-0.0 · turn 3 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:03:38.649Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

The view is truncated. Let me read the full workspace view to see the complete goal.

Now I can see the full goal. After `proc.`, we have:

Left side (CPA(ElGamal, A).main):
```
(pk, sk) <@ ElGamal.kg()
(m0, m1) <@ A.choose(pk)
b <$ {0,1}
c <@ ElGamal.enc(pk, if b then m1 else m0)
b' <@ A.guess(c)
```

Right side (DDH0(DDHAdv(A)).main):
```
x <$ dt
y <$ dt
b <@ DDHAdv(A).guess(g ^ x, g ^ y, g ^ (x * y))


```

Now looking at what `DDHAdv(A).guess` actually does internally—it runs the adversary's choose and guess procedures with the DDH challenge values, then returns whether the adversary's guess matches a randomly sampled bit. So the right side's `b` is the result of that comparison, and the postcondition is checking whether this matches the left side's `b'`.

To prove these are equivalent, I need to inline the ElGamal key generation and encryption on the left side, and expand the DDH adversary's guess procedure on the right. Once everything is unfolded, I should be able to match up the corresponding operations between both sides. Let me try using `inline *` to expand all the module calls at once, then work through the proof with the standard tactics.

```
