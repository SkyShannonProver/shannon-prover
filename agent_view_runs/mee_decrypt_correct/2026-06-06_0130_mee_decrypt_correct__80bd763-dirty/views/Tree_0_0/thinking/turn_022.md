# Tree-0.0 · turn 22 · commit_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:45:11.525Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (true).`

---

The `while (true)` probe was accepted and produces:

Goal (6 remaining — was 5, now +1 from the while body):
```
pre = i < size c
(1)  ci <- nth witness c i
(2)  pi <@ PRPc.PseudoRP.fi(ek, ci)
(3)  padded <- padded ++ [s - pi]
(4)  s <- ci
(5)  i <- i + 1
post = true
```

This is a hoare goal for the while loop body with `pre = i < size c` and `post = true`. 

The body trivially terminates and establishes `true`, so I should be able to close this with a tactic that applies weakest precondition reasoning and then solves the resulting trivial goal. Before committing the while loop, I want to check if I can inline the `PRPc.PseudoRP.fi` function in this context to simplify the proof.
