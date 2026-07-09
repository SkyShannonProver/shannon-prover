# Tree-0.1.1 · turn 3 · commit_tactic

<!-- session db364dba-374a-4d5e-a03e-0f24d9575646 · 2026-06-02T03:04:15.594Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={glob LRO, glob Log}).`

---

The `rnd.` tactic was accepted. Let me read the full view to see the postcondition properly.

Good. The `rnd` tactic was accepted. Now the goal shows:
- LHS: init, kp <$ dkeys, (pk,sk) <- kp, A.a1(pk) — 4 statements
- RHS: init, (pk,sk) <$ dkeys, A.a1(pk) — 3 statements

The postcondition has some trivial conditions (`bR = bR`, `bL = bL`) from the `rnd` step. The real content is:
```
(glob A){1} = (glob A){2} /\


LRO.m{1} = LRO.m{2} /\
Log.qs{1} = Log.qs{2} /\
pk{1} = pk{2} /\
sk{1} = sk{2} /\ m0{1} = m0{2} /\ m1{1} = m1{2}
```

Now I need to handle the A.a1 call on both sides. I'll use `call` to match this procedure invocation, and I need to set up an invariant for the oracle that captures the equivalence between the two sides.

Since both sides call `Log(LRO)` with identical state, I can use an invariant stating that the global variables LRO and Log remain equal. This should let the `call` tactic generate the right subgoals for verifying that the oracle preserves this invariant and that the precondition holds before the call.
