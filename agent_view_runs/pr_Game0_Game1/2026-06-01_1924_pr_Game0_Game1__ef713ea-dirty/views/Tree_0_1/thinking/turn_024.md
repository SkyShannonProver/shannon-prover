# Tree-0.1 · turn 24 · fresh_restart

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:55:36.551Z -->

**Intent:** `fresh_restart`  
**Payload:** `(none)`

---

Still rejected. So `Log.qs{1} = Log.qs{2}` is also rejected. Only `true` works.

Wait, I just realized something. Maybe the issue is that `call (_: inv, bad)` in EasyCrypt requires the invariant to be about the oracle's OWN state, not about arbitrary module variables. The oracle is `Log(LRO)`, and `Log.qs` is a variable of the `Log` module, and `LRO.m` is a variable of `LRO`. 

The oracle `Log(LRO).o` modifies both `Log.qs` and `LRO.m`, so those should count as the oracle's state. But `Game1.r` in the bad event is a module variable of `Game1` itself, not part of the oracle. Even though `Game1.r` doesn't change during the `a2` call since it was fixed during encryption, maybe EasyCrypt still won't allow the bad event to reference variables outside the oracle's scope.

Let me try a different bad event that only uses oracle variables. I already tested `Game1.r{2} \in Log.qs{2}` and it worked, so maybe the issue is with how I'm specifying the invariant syntax. In EasyCrypt, the `call` statement for abstract adversaries expects the invariant to be about `glob O` specifically, so I need to make sure the invariant has the right form.

For the "upto bad" variant, the invariant should reference the oracle's state like `glob Log` and `glob LRO`, but maybe EasyCrypt requires the invariant to be unilateral rather than relational in this context.

That would explain why `true` works but `Log.qs{1} = Log.qs{2}` doesn't—the latter is relational. But that seems odd since standard `call (_: Inv)` uses relational invariants like `={glob Log, glob LRO}`.

Maybe the "upto bad" form needs a different structure with separate invariants for each side. Let me try a different approach using `seq` to split the proof and sidestep this `call` issue entirely.

After inlining, I have the LHS and RHS states at different points. I'll use `seq` to create an intermediate invariant at the boundary that captures either the good case where b, c, and glob A agree with matching oracle maps, or the bad case where the game's random value appears in the query log.

For the second part with just the a2 call, I need to prove the equivalence from this intermediate state to the postcondition. If the bad event has occurred, the postcondition holds trivially. If we're in the good case, I'd want to use a call rule with matching global state, but the oracle map still has that mismatch issue—even with the seq split, a2 sees different LRO.m states between the two sides.

Let me try something different: what if the intermediate invariant itself forces LRO.m to be equal? That won't work though, since they genuinely diverge after encryption. Maybe I should abandon the equiv approach entirely and try using eager instead. But before that, let me explore whether there's a three-argument form of the call rule that could help—something that lets me specify the invariant and handle the bad events more explicitly.

Actually, I'm wondering if the issue is that the postcondition `res{1} = res{2} \/ bad{2}` doesn't logically follow from what I'm asserting without additional reasoning. What if I use conseq to strengthen the postcondition first, making it something like `={b, b', glob A, glob Log} \/ (Game1.r \in Log.qs){2}`? That might give the call rule what it needs to succeed.

But I'm starting to think the real problem is how EasyCrypt derives the oracle goals from the invariant itself. Let me try a different tactic entirely — maybe I should use eager to handle this, or go back to the beginning with fresh_restart and attempt a completely different proof strategy.
