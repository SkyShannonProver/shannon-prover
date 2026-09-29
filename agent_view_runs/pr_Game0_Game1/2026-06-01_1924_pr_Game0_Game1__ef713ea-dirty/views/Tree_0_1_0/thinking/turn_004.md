# Tree-0.1.0 · turn 4 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:56:57.855Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

The wp consumed the deterministic assignments on the LHS (pk0 <- pk, m <- if b then m0 else m1). The remaining programs now have 5 stmts on LHS and 4 on RHS. Let me read the full view to see the exact postcondition.

Actually, looking at the preview, the LHS now has:
1. Log(LRO).init()
2. kp <$ dkeys
3. (pk, sk) <- kp
4. (m0, m1) <@ A(Log(LRO)).a1(pk)


5. b <$ {0,1}

RHS:
1. Log(LRO).init()
2. (pk, sk) <$ dkeys
3. (m0, m1) <@ A(Log(LRO)).a1(pk)
4. b <$ {0,1}

The postcondition is truncated, but after the wp absorbed those deterministic assignments, it should just have the equalities with pk0 replaced by pk and m replaced by the conditional. Now I need to couple the b samplings using rnd.
