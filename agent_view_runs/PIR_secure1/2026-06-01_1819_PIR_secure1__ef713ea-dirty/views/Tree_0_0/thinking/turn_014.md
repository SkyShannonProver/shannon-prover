# Tree-0.0 · turn 14 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:28:32.082Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto.`

---

`auto.` was accepted and closes goal 1 (the call spec), moving to goal 2 with 1 remaining goal. The next goal is:

```
pre = true
(1------)  j <- 0
(2------)  (PIR.s, PIR.s') <- ([], [])
(3------)  while (j < Top.N) { ... }
(4------)  r <@ PIR.query(PIR.s)

post =
  (PIR.s'{1} = PIR.s'{2} /\ true) &&
  forall (result_L result_R : word),
  result_L = result_R /\ true => PIR.s{1} = PIR.s{2}
```

The second goal requires proving that after the procedure body (excluding the final query call), the state lists are equal, and that equal query results imply the initial states were equal. I'll commit `auto.` and then use another `call (_: true).` for the remaining query, followed by handling the initialization and loop invariant.

Committing now...
