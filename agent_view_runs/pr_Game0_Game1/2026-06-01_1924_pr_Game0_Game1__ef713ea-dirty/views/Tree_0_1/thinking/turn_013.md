# Tree-0.1 · turn 13 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:46:38.182Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={Log.qs}, (Game1.r \in Log.qs){2}).`

---

OK, even `={Log.qs, LRO.m}` with extra parens is rejected. But `true` works. What's the difference?

Wait, I think I understand now. Maybe the issue is that `call (_: inv, bad)` generates not just the oracle goals but also a PRECONDITION obligation. The precondition needs `inv` to hold BEFORE the call. With `true`, the precondition is trivially satisfied. But with `={Log.qs, LRO.m}`, the precondition `={Log.qs, LRO.m}` needs to be established from the previous code, and EasyCrypt checks at call-generation time whether the postcondition of the call is compatible with the overall postcondition.
 
Hmm, but that check should happen after the tactic runs, not while it's being applied. Unless EasyCrypt's `call` tactic actually validates at application time whether the postcondition is entailed by combining the call's postcondition with the invariant—if that combined result doesn't imply the overall postcondition, the tactic fails immediately.

Looking at the specific case with `call (_: ={Log.qs, LRO.m}, bad)`, the call postcondition becomes `(={b'} /\ ={Log.qs, LRO.m}) \/ bad`, and combined with the context `={b}`, this should entail the overall postcondition `(b'{1} = b{1}) = (b'{2} = b{2}) \/ bad`. If the good case holds, the equality chain works out; if bad is true, the disjunct covers it. So the implication should go through, unless EasyCrypt is stricter about the exact form it expects for the result.

Actually, I'm noticing the full postcondition is `(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})`, which is a disjunction where the left side is an equality of equalities—maybe EasyCrypt is having trouble recognizing this as the right shape. Log.qs{2}`.

But the `call (_: inv, bad)` produces postcondition `(={res} /\ inv) \/ bad`. For this to entail the overall postcondition, we need:
- `(={b'} /\ inv) => ((b'{1} = b{1}) = (b'{2} = b{2}))` given `={b}`
- `bad => (Game1.r{2} \in Log.qs{2})`

The second is trivial (they're the same). The first: `={b', b}` gives `(b'{1} = b{1}) = (b'{2} = b{2})`, which is correct. And `inv` is extra information that's not needed.

Wait, but `={b'}` after the call... In EasyCrypt, the `call` for an abstract adversary generates `={res}` when the oracle invariant ensures `={res}` for each oracle call and `={args}` for the adversary call. With the "upto bad" call, `={res}` holds only when `!bad`. So the postcondition from `call (_: inv, bad)` should be `(={res} /\ inv) \/ bad{2}`, which means the overall postcondition becomes `(b'{1} = b{1}) = (b'{2} = b{2}) \/ bad{2}`. Now I need to verify that the call postcondition entails this.

I'm checking whether the postcondition from the call statement logically implies the overall postcondition, considering what variables are in scope and what equalities have been established. So the real issue might be that when EasyCrypt applies `call` with the invariant and bad event, it's checking whether the postcondition `={Log.qs, LRO.m}` can be satisfied alongside the equality constraints from the call's return, but `b` isn't being tracked through the call so the proof fails. Let me reconsider what's actually happening after the call executes. I'm going in circles trying to figure out the precondition structure. Let me step back and try separating the code at the call boundary first — I can use `seq` to split the proof into the deterministic part before the call and the call itself, then handle each piece independently.

Writing proof tactics... I'm carefully tracking the step counts on each side to verify the intermediate invariant holds at the right point. After the initial setup and random sampling, both sides converge to the same remaining code where the adversary makes its second query.

The issue is that using `call` directly still requires matching postconditions, which creates the same problem I was trying to avoid. Let me reconsider the approach entirely.

Instead of wrestling with `byequiv` and disjunctive postconditions, I'll establish a simpler probability inequality using a `have` statement that bounds the original game against a modified game where I explicitly track the bad event. The postcondition becomes an implication rather than an equality, which should be easier to handle with `byequiv`.

Then I can apply transitivity and use `mu_or` to decompose the probability. The tricky part is still the `a2` call — I need to figure out whether I can avoid the "upto bad" pattern entirely and just prove the implication directly, but the oracle state mismatch between games remains a blocker.

Let me try abandoning `byequiv` altogether and instead build up the proof using probability-level reasoning with `byphoare`. The idea would be to decompose the original game's probability into disjoint cases, but that runs into the fundamental issue that `Game1.r` doesn't exist in the `BR93_CPA` context, so I can't directly relate the two games this way. Trying different syntax variations for the call tactic...

Let me test a simpler version with just the equality invariant to see if that parses correctly.
