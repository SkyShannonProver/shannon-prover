# Tree-0.1 · turn 14 · commit_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:40:42.443Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (true).`

---

`while (true).` was accepted. The first subgoal it generates is the loop body with `pre = i < size c` and `post = true`. This should be closable easily. The loop body has a call to `PRPc.PseudoRP.fi`, but since `post = true`, I just need to show the call terminates, which should be automatic.

Let me commit `while (true).` and then try to close the body with something like `wp; call (_: true); wp; skip; auto.` or just `auto.`.

Actually, looking at the body:
```
(1) ci <- nth witness c i
```

The remaining statements handle extracting the next element, calling the pseudorandom function, appending to the padded list, updating the state, and incrementing the counter. With `post = true`, I can use `call (_: true)` to handle the function call and then let `wp` or `auto` handle the rest of the assignments and loop increment.
