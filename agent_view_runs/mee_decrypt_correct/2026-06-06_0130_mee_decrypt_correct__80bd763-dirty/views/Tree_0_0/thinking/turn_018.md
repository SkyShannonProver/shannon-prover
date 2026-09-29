# Tree-0.0 · turn 18 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:41:50.620Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (0 <= i <= size c /\ ek = _ek /\ mk = _mk /\ p = None /\ c = behead _c /\ padded = cbc_dec AESi _ek (head witness _c) (take i c) /\ s = last (head witness _c) (take i c)) (size c - i).`

---

The `seq` probe was accepted and produced 5 subgoals. The first subgoal is:

```
pre = exists (c0 : block list), p = None /\ (ek, mk) = key /\ s = head witness c0 /\ c = behead c0 /\ padded = [] /\ i = 0 /\ (key, c0).`1 = (_ek, _mk) /\ (key, c0).`2 = _c

while (i < size c) {
    ci <- nth witness c i
    pi <@ PRPc.PseudoRP.fi(ek, ci)
    padded <- padded ++ [s - pi]
    s <- ci
    i <- i + 1
}

post = true
```

The postcondition being just `true` is unexpected — I'd normally expect the `seq` decomposition to use an intermediate predicate there. Let me reconsider how the phoare `seq` tactic splits things up, since this doesn't match what I initially thought it would produce.

With 5 subgoals total, it looks like the decomposition is creating multiple pieces: the while loop with some postcondition, the suffix code with the original postcondition, and then several side conditions about probability and predicate relationships. I need to see the full goal list to understand what's actually being asked here. I'm realizing the `seq` tactic is breaking this down into multiple subgoals: the losslessness condition for the while loop itself, probability side conditions, a standard Hoare triple for the loop, the probabilistic postcondition for the suffix code, and some gluing constraint to tie it all together. This is more complex than I expected, so let me just commit and work through each goal systematically.

Actually, maybe I should try the `while` tactic directly instead—it typically generates four cleaner subgoals: invariant preservation, initial condition, termination via a variant, and the final condition where the invariant plus the negated guard implies the postcondition. That's still multiple goals but more structured and easier to reason about. Writing while loop invariant...
