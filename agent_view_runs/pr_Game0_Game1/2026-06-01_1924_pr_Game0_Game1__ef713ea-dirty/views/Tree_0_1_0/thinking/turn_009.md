# Tree-0.1.0 · turn 9 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:58:05.114Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Good, `inline*` was accepted. Now the programs are:

LHS:
1. Log.qs <- []
2. LRO.m <- empty
3. kp <$ dkeys
4. (pk, sk) <- kp

RHS:
1. Log.qs <- []
2. LRO.m <- empty
3. (pk, sk) <$ dkeys

The postcondition is complex (truncated). Let me read the full view to see the exact postcondition, or just try `wp; rnd; skip; progress.` or `auto`.


Let me work through `wp; rnd; skip; progress.` step by step, starting with `wp.`
