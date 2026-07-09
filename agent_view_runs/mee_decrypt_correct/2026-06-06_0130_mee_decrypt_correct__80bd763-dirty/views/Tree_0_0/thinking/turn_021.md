# Tree-0.0 · turn 21 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:44:57.429Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (true).`

---

"invalid arguments" — the `while` tactic with `(true) (size c - i)` was rejected. This might be because the current goal is NOT a phoare goal but rather a hoare goal (since `post = true`). Let me check.

Wait, the goal shows:
```
Context : hr: {...}
pre = ...
(1--)  while (i < size c) { ... }
post = true
```

But there's no `Bound` line! In the previous goal, the Bound was `[=] 1%r`. But this first seq-decomposed goal might be a hoare goal (not phoare). 

If it's hoare, `while` takes a different form — just `while (INVARIANT)` without a variant. The `seq` tactic might have converted the phoare goal into a hoare goal, which would explain why the bound disappeared and why my tactic syntax failed. Let me look at the full workspace to see what's actually happening.

The goal type is `hoare`, not `phoare`. So this first goal is a hoare goal with `post = true`. In hoare logic, the while tactic takes just `while (INVARIANT)` without a variant.

So for this hoare goal with `post = true`, I just need `while (true)` (invariant = true, since post = true). Let me try:

```
while (true).
```

But wait, can hoare while with invariant=true handle the call inside the loop? In hoare logic, `while (INVARIANT)` generates:
1. `hoare [body : INVARIANT /\ guard ==> INVARIANT]` — body preserves invariant
2. `INVARIANT /\ !guard => post` — post after loop

For invariant = true and post = true, both conditions are trivially satisfied. The body still needs to handle the call though, and in hoare logic both `call` and `inline` should work for processing function calls.

For a `while (true)` loop in hoare logic, the body goal becomes `hoare [body : true /\ (i < size c) ==> true]`, which is trivially true. The key is that EC needs to verify the call inside the body terminates, which it can since the body is just a return statement. In hoare triples, calls are resolved by matching against known hoare specifications.

Let me just try the simple `while (true)` approach — if the body goal is trivially closeable, we're done; otherwise I'll need to handle the call explicitly.
