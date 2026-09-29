# Tree-0.1 · turn 26 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:56:07.567Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_ : ={glob A, glob LRO} ==> !(Game1.r{2} \in Log.qs{2}) => ={res}) : (Game1.r \in Log.qs) => //.`

---

I'm back to the original probability goal. Now let me try a completely different approach.

The goal is:
```
Pr[BR93_CPA(A).main() @ &m : res] <= Pr[Game1.main() @ &m : res] + Pr[Game1.main() @ &m : Game1.r \in Log.qs]
```

This is `Pr[G0 : E] <= Pr[G1 : E] + Pr[G1 : F]`.

Let me try using `byequiv` with the "upto bad" annotation. 

I think the right EasyCrypt syntax uses `byequiv` with a bad event specification that tells the tactic to decompose the probability bound automatically—the bad event here is `Game1.r \in Log.qs`, which should split the goal into the equivalence part and the probability of the bad event occurring.

Actually, I'm second-guessing whether `byequiv (_ : ... ==> ...) : bad` is even valid syntax. Let me think through what I've seen work: without the bad annotation, `byequiv` gives me `Pr[G0 : E] <= Pr[G1 : E \/ F]`, and then I manually apply the union bound. With the annotation, it should directly produce `Pr[G0 : E] <= Pr[G1 : E] + Pr[G1 : F]`. I need to test this to see what EasyCrypt actually accepts. I think the `:bad` annotation might unlock a special "upto bad" mode in pRHL proofs where the `call` tactic behaves differently—generating goals that account for when the bad event occurs. So my approach would be to use `byequiv` with the `:bad` annotation to enter this mode, then leverage `call` with an invariant that holds as long as bad doesn't happen, letting the coupling break when it does.
