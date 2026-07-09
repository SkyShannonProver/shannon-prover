# Tree-0.1 · turn 24 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:33:15.059Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (={PIR.s, j}); last by auto => /> /#.`

---

Now the query calls are gone and the while loop is the last instruction. The goal is:

```
pre = i{2} = arg{2} /\ i{1} = arg{1}

(1) j <- 0
(2) (PIR.s, PIR.s') <- ([], [])
(3) while (j < Top.N) { ... }

post = PIR.s{1} = a <=> PIR.s{2} = a
```

Now I can use `while (={PIR.s, j}).` to handle the loop. 

The invariant `={PIR.s, j}` captures that both executions maintain identical values for these variables, which directly gives me the postcondition. I need to verify the loop body preserves this invariant and that initialization establishes it, then apply the while tactic.
