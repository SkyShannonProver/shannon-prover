# Tree-0.1 · turn 23 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:33:01.987Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc; inline *; wp.`

---

`proc; inline *; wp.` WORKED! The probe was accepted, and the resulting goal after probe shows:

```
pre = i{2} = arg{2} /\ i{1} = arg{1}

(1------)  j <- 0
(2------)  (PIR.s, PIR.s') <- ([], [])
(3------)  while (j < Top.N) { ... }
(3.3----)    j <- j + 1
(3------)  }

post = PIR.s{1} = a <=> PIR.s{2} = a


```

Now that the inlining has absorbed the query calls, the while loop is what remains to prove. I'll apply the while loop tactic with the invariant tracking PIR.s and j, then handle the loop body with weakest precondition and randomness reasoning.

Since PIR.s updates identically regardless of the initial difference between the two argument values, I can use the identity coupling to establish the invariant, then finish with automation for the initialization step.

```
