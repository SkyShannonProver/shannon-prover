# Tree-0.0 · turn 5 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:23:25.566Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp.`

---

`sim.` was accepted and leaves the residual goal:

```
forall &1 &2, true => i{1} = i{2}
```

This is problematic — `sim.` requires `={i}` but the precondition is `true`, not `={i}`. The `sim` tactic inferred that all variables should be equal, including `i`, but our precondition is `true` (no constraint on `i`).

This means `sim.` doesn't work directly because it generates an unprovable side condition (`i{1} = i{2}` from `true`).


I need to step back and use a weaker invariant instead. Since `PIR.s` doesn't actually depend on `i` — both branches add `j` to `s` when `b = true` — I should prove this by only requiring `={PIR.s, j}` rather than forcing `i` to be equal. I could either specify this invariant explicitly with `sim`, or manually unroll the loop with `wp` and handle the random assignment and skip separately.

But `sim` requires the initial states to match on `i`, which we can't establish from `true`. So I'll need to go manual: after `proc.`, I'll handle the setup, the while loop with the weaker invariant, and then the tail with the query calls and return — using `conseq` to manage the postcondition since the queries don't touch `PIR.s`. I'm working through the postcondition `PIR.s{1} = PIR.s{2}` and realizing that since `query` only reads from state without modifying it, I can use `conseq` to weaken the postcondition to just `={PIR.s}` before those calls. The tricky part is that my precondition starts as `true`, not `={PIR.s}`, so I need to think about how to bridge that gap. Let me try a standard pRHL pattern: start with `proc`, set up the while loop with an invariant that tracks `={PIR.s, j}`, then handle the loop body with weakest precondition reasoning and randomness, finishing with `skip`.

Trying `auto` to handle the remaining goals...

Actually, I'm realizing the core issue: after `proc.`, the programs are synchronized and `inline *` might not work the way I expect. Let me try targeting specific procedures with `inline{1} PIR.query.` or `inline{2} PIR.query.` instead.

But wait—since the postcondition is `={PIR.s}` and `query` doesn't modify `PIR.s`, maybe I can use `conseq` to adjust the goal and avoid needing to inline at all.

Or I could try a different tactic entirely. The problem is that `sim.` leaves me with `i{1} = i{2}` which I can't prove from `true`, so I need to give `sim` a weaker loop invariant. Let me try specifying the invariant directly with `sim (: ={PIR.s, j}).` or just `sim (: ={PIR.s}).` to guide the tactic toward what's actually provable.

Looking back at the original proof of PIR_secure2, it uses `proc; inline *; wp.` but my `inline *` got rejected, which makes me wonder if the eval copy has different code or module structure than the source file. Checking the preconditions more carefully, both PIR_secure1 and PIR_secure2 start with `true`, and PIR_secure2 should be provable with the same approach.

The error message was just "EasyCrypt rejected the committed tactic," which isn't very helpful. Let me try a different strategy—maybe `wp.` alone will work, or I could try `sp.` to handle the initialization first, or be more specific with `inline PIR.query.` instead of the wildcard.

Actually, thinking about it more, after `proc.` both sides show as synchronized, which might mean `inline *` fails because there's nothing distinct to inline—the `query` calls are identical on both sides. But `inline` should still work on concrete procedure calls regardless. Let me try `wp.` to see if it can propagate the postcondition backwards through the deterministic assignments, though I'm not sure it'll handle the procedure calls. Another option is to use `seq 3 3: (={PIR.s}).` to cut the proof at the while loop boundary and require the state equality after the loop.

Actually, maybe I should just try `sim` with parameters—something like `sim / {i}.` to tell the tactic to ignore the `i` variable and only couple the rest, since `PIR.s` doesn't depend on it anyway. I'm not entirely sure about the exact EasyCrypt syntax though, so I should check the tactic forms or try it directly.

Looking at the goal after `sim.`, it's clear that `sim` proved everything equal except for `i{1} = i{2}`, which means if I can exclude `i` from the equality requirement, this should work. The real issue is that while the programs are syntactically identical, `sim` also requires the precondition to entail equality of all variables, and `true` doesn't give us that for `i`. But semantically, the proof is actually sound.

Since `PIR.s` doesn't depend on `i`, I need to either use a more targeted manual approach or find a way to tell `sim` to ignore certain variables. Let me try working through this step by step without `proc.` at all—maybe using `byequiv` with a lemma or trying a different tactic sequence like `wp` followed by handling the while loop manually.

I'm wondering if `wp` can actually handle the `query` procedure calls here since they're purely functional—some versions of EasyCrypt can work through concrete pure procedures. But more likely, after `proc.`, I need to handle the tail by leveraging the fact that `query` doesn't modify `PIR.s` and my postcondition only cares about that variable.

I'm thinking about using `seq` to cut right after the while loop, which is statement 3, so I'd write `seq 3 3` to establish that `PIR.s` is equal at that point, then handle the query calls afterward.

Actually, I'm overcomplicating this. Let me explore what the `sim` tactic can do—it has variants like `sim / R` for specific variables or `sim / : P` for relations, so maybe one of those forms will work better here. Hmm, I'm not sure about the exact syntax. Let me try `sim / {2 : i}.` — no, that doesn't look right either.

Actually, I know in EasyCrypt there's a `sim` variant that allows specifying which variables should be equal. The syntax might be:

`sim (: true ==> ={PIR.s}).` or `sim / (i{1} = i{2}).`

But I'm not confident about the syntax. Let me try the manual approach instead.

Actually, let me try yet another approach. What about using `conseq` to weaken the precondition? Wait, the precondition is `true`, we can't really weaken further. But we could use `conseq` to change the postcondition.

Let me just test whether `wp` works here, even with the procedure calls involved — if they're concrete and simple enough, it might handle them.
