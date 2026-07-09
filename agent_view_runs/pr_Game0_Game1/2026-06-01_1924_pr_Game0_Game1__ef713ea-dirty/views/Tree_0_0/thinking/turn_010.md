# Tree-0.0 · turn 10 · commit_tactic

<!-- session a461d2c6-c4cb-4e5e-89e6-7f23ff5db8a4 · 2026-06-02T02:38:21.003Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_ : true); auto.`

---

`sim` handled most of the prefix but left the keygen part: `Log(LRO).init(); kp <$ dkeys; (pk,sk) <- kp` vs `Log(LRO).init(); (pk,sk) <$ dkeys`. I need to show these are equivalent.

The remaining goal has:
Left: `Log(LRO).init(); kp <$ dkeys; (pk,sk) <- kp`
Right: `Log(LRO).init(); (pk,sk) <$ dkeys`

Post: `sk{1} = sk{2} /\ pk{1} = pk{2} /\ Log.qs{1} = Log.qs{2} /\ LRO.m{1} = LRO.m{2} /\ (glob A){1} = (glob A){2}`


I'll use `wp` to push through the deterministic assignment, then `rnd` to handle the sampling equivalence, followed by `call` for the initialization and `auto` to finish up.

Actually, `wp` processes deterministic code from the end of both programs, so it'll only handle the left's `(pk,sk) <- kp` since the right has a random sampling. After that, both sides have the log initialization followed by their respective sampling statements, which `rnd` can then equate by relating how `kp` is sampled on the left versus destructured on the right. Trying different tactic approaches...

I need to be careful about how `wp` handles the destructured pair assignment—after it processes the left side, the postcondition will reference `kp` directly, so I need `rnd` to properly match that against the right side's `(pk,sk)` tuple. Let me experiment with a few variations: either applying `rnd` with an explicit identity function on the pair, or combining it with `call`, `skip`, and `smt()` to see what works.

Actually, looking at the goal more carefully, both sides start with the same `Log(LRO).init()` call, then diverge into sampling—the left uses an intermediate variable `kp` while the right samples directly into the tuple. The `call` tactic should handle the initialization, but I'm uncertain whether it processes from the end or can target specific calls in pRHL. I'm realizing that `call` in pRHL requires a module invariant for the oracle, but `Log(LRO).init()` doesn't take an oracle argument—it just calls `H.init()` internally, which complicates how to set up the invariant for the call tactic. Let me try just running `auto` to see if it handles the entire subgoal automatically. If that doesn't work, I'll need to be more explicit with the call tactic, specifying the postcondition relating the global state of both modules—though I need to be careful about the exact syntax since `call` doesn't use `==>` for its invariant specification.
