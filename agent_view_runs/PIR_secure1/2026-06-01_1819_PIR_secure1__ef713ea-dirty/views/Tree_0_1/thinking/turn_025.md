# Tree-0.1 · turn 25 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:33:34.170Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={PIR.s, j}); last by auto => /> /#.`

---

`while (={PIR.s, j}); last by auto => /> /#.` was accepted! The resulting goal after the probe is the loop body preservation:

```
pre = (PIR.s{1} = PIR.s{2} /\ j{1} = j{2}) /\ j{1} < Top.N /\ j{2} < Top.N

(1) b <$ {0,1}
(2) if (j = i) {
      if (b) { PIR.s <- j :: PIR.s }
      else { PIR.s' <- j :: PIR.s' }
    } else {
      if (b) { PIR.s <- j :: PIR.s; PIR.s' <- j :: PIR.s' }
    }
(3) j <- j + 1

post = (PIR.s{1} = PIR.s{2} /\ j{1} = j{2}) /\ (j{1} < Top.N <=> j{2} < Top.N)
```

The initialization subgoal is already handled by `last by auto => /> /#.`. Now I'm working through the loop body to verify it maintains the invariant, focusing on how the updates to `PIR.s` interact with the pre and post conditions.

The crucial part is that `PIR.s` gets updated to `j :: PIR.s` exactly when `b = true`, and this update preserves the equality relation between the two copies when I use identity coupling on `b`. I'll apply weakest precondition reasoning to absorb the increment and conditional, couple `b` with itself, then close out the resulting pure goal.
