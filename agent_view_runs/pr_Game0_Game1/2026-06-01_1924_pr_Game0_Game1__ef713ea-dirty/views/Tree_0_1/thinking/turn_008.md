# Tree-0.1 · turn 8 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:42:13.108Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true, (Game1.r \in Log.qs){2}).`

---

Good, I can see the checkpoint options. Let me rewind all the way back to before the `byequiv` (checkpoint 1) and try a completely different approach.

Actually, let me think about what approach to take.

Option 1: Rewind to the beginning and try the `byequiv` with a different postcondition or use a probability-level tactic.

Option 2: Rewind to just before the `inline` and try a different proof structure (without inlining keygen/enc).

Option 3: Stay at the current state (after inline) and try a different approach for the `a2` call.


I'm realizing the "upto bad" call syntax might need the `glob A` included in the invariant, or perhaps the argument ordering is off. Let me reconsider the EasyCrypt documentation for the `call` tactic—specifically how to structure the invariant, bad event predicate, and loss invariant parameters correctly.

Trying different formulations of the call with the invariant about `Log.qs` equality and the bad event being when `Game1.r` appears in the log, but I keep hitting rejections, possibly because `eq_except` or `pred1` aren't working as expected...

Let me test whether the `call (_: inv, bad)` syntax itself is valid by using a trivial invariant like `true` to isolate whether the problem is syntactic or with my invariant formulation.
