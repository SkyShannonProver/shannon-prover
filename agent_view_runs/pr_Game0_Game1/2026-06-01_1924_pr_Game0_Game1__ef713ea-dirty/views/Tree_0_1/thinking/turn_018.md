# Tree-0.1 · turn 18 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:49:17.398Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> _; proc; call (LRO_o_ll _); auto=> /=; apply dptxt_ll.`

---

The current goal is:
```
forall _, phoare[ Log(LRO).o {&2}: true /\ true ==> true /\ true] = 1%r
```

This simplifies to: `phoare[Log(LRO).o : true ==> true] = 1%r`, which is just losslessness of `Log(LRO).o` on side 2.

This is the same as `islossless Log(LRO).o`. Let me prove it the same way:


I'll move past the universal quantifier, switch to procedural mode, apply the losslessness lemma for `LRO_o_ll`, simplify the goal, and then use the losslessness property of the differential privacy text.
