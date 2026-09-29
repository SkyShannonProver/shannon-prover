# Tree-0.1.0 · turn 5 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:57:08.053Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={Log.qs, LRO.m}).`

---

Good, `rnd` was accepted. The programs now have 4 stmts on LHS, 3 on RHS. The postcondition has the `forall bL/bR` quantifiers from the rnd coupling. Now I need to handle the A.a1 call.

The remaining programs:
LHS:
1. Log(LRO).init()
2. kp <$ dkeys
3. (pk, sk) <- kp
4. (m0, m1) <@ A(Log(LRO)).a1(pk)


RHS:
1. Log(LRO).init()
2. (pk, sk) <$ dkeys
3. (m0, m1) <@ A(Log(LRO)).a1(pk)

For the A.a1 call, I'll apply a relational call tactic that establishes the oracle invariant on Log(LRO), ensuring the query sets and LRO.m values remain equal between the two sides.

Now I need to verify that this invariant holds through the oracle procedure itself.
