# Tree-0.1.0 · turn 10 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:58:11.535Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

Good, `wp` was accepted. Now I see the postcondition has `let pk_L = kp{1}.\`1 in ...`. The programs are now:

LHS:
1. Log.qs <- []
2. LRO.m <- empty
3. kp <$ dkeys

RHS:
1. Log.qs <- []
2. LRO.m <- empty
3. (pk, sk) <$ dkeys

I need to couple the samplings. Both sample from `dkeys`. On the LHS, `kp` is a pair `(pkey * skey)`. On the RHS, `(pk, sk)` is the destructured form.


Let me try using `rnd.` to establish the coupling between these two samplings.
