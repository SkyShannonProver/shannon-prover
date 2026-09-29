# Tree-0.1.0 · turn 2 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:55:51.616Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 7 4 : (={glob A, Log.qs, LRO.m, b, pk, sk, m0, m1} /\ pk0{1} = pk{1} /\ m{1} = (if b{1} then m0{1} else m1{1})).`

---

The inline was accepted. The view is truncated in the preview. Let me read the full workspace view to see the expanded goal.

Now I can see the full goal after inlining LRO.o on the left. The LHS now shows:

```
Log(LRO).init()                 ( 1)
kp <$ dkeys                     ( 2)
(pk, sk) <- kp                  ( 3)
(m0, m1) <@ A(Log(LRO)).a1(pk)  ( 4)
b <$ {0,1}                      ( 5)
pk0 <- pk                       ( 6)


m <- if b then m0 else m1       ( 7)
r <$ drand                      ( 8)
x <- r                          ( 9)
r0 <$ dptxt                     (10)
if (x \notin LRO.m) {           (11)
  LRO.m <- LRO.m.[x <- r0]      (11.1)
}                               (11)
h <- oget LRO.m.[x]             (12)
c <- (f pk0 r, h +^ m)          (13)
b' <@ A(Log(LRO)).a2(c)         (14)
```

And the RHS mirrors this structure, showing how the adversary interacts with the logged oracle throughout the game. When the oracle hasn't been queried on that input, it returns a fresh sample matching the right-hand side, but when it has been queried, it returns the cached value—which differs from the right-hand side but triggers the bad event. My approach is to use sequence composition to split the game at the divergence point, handle the common prefix separately, then reason about the remainder with the oracle inlined.

The prefix ends after statement 7 on the left side and statement 4 on the right side, so I'll establish the sequence cut there. At that point, the global state, query log, oracle map, the bit `b`, and the key material are all synchronized between the two games, with the message selection determined by `b` on the right side. Let me commit to this cut point.

Now I need to verify the equivalence more carefully. The left side goes through initialization, samples the keypair, destructures it, calls the oracle, samples `b`, stores `pk`, and computes the message. The right side initializes, directly samples the keypair, calls the oracle, and samples `b`. The keygen operations are equivalent since both produce the same `pk` and `sk`, the oracle call produces identical results with the same state, and `b` is sampled identically. The left side's extra assignments just store values that are already determined, so the invariant tracks these synchronized values across both games.

Setting up the invariant...

I need to verify which variables are actually assigned at each point. After 7 statements on the left side, I have `b, m0, m1, m, pk, pk0, sk, kp`, while the right side only has `b, m0, m1, pk, sk` after 4 statements. The variables `x` and `r0` haven't been assigned yet on the left, and `Game1.r` and `h` are still unassigned on the right. My invariant should handle this correctly. Let me also double-check the precondition—it includes `(glob A){1} = (glob A){2}` and `LRO.m{1} = LRO.m{2}`, but notably `Log.qs` isn't part of it.

After `Log(LRO).init()` runs, `Log.qs` gets initialized to an empty list on both sides, so that equality is preserved. The `LRO.m` field gets set to `empty` when `LRO.init()` is called from within the Log initialization, maintaining the invariant that `LRO.m{1} = LRO.m{2}`.

Now I need to verify the invariant is actually sound—specifically, I don't need to track `r{1}` and `x{1}` since they haven't been assigned yet at the point where I'm checking this. Let me finalize the `seq` statement.
