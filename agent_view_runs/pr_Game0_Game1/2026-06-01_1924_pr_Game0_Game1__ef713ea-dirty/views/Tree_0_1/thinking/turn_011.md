# Tree-0.1 · turn 11 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:44:09.286Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={Log.qs, LRO.m}, (Game1.r \in Log.qs){2}).`

---

Still rejected. The issue isn't the invariant expression itself (since `true` worked). Let me think about what's different.

With `true`: `call (_: true, (Game1.r \in Log.qs){2}).` — ACCEPTED
With the forall invariant: REJECTED

Maybe the issue is that the "upto bad" call with a non-trivial invariant generates goals that EasyCrypt can't type-check, or the invariant references variables that aren't in scope for the oracle.

Wait — `Game1.r` is a module variable. In the oracle context (`Log(LRO).o`), `Game1.r` is a global variable that's readable. 

But maybe EasyCrypt restricts which module variables can appear in the invariant of a `call` for an abstract adversary. The `call (_: inv, bad)` generates several proof obligations, including oracle preservation and bad monotonicity. For the monotonicity check, I need to show that the bad event `Game1.r \in Log.qs` is preserved — which should hold since `Log.qs` only grows — but something about how EasyCrypt handles this with the forall invariant seems to be failing.

Actually, I think the real issue is that when using a `forall` invariant, EasyCrypt might generate goals that don't type-check. The invariant `forall x, x <> Game1.r{2} => LRO.m{1}.[x] = LRO.m{2}.[x]` uses `{1}` and `{2}` to refer to the oracle's left and right memories, not the main game's. So `Game1.r{2}` might not be well-typed in that oracle context — the module variable reference could be invalid when the invariant is interpreted as an oracle goal. I'm going to test a simpler invariant combining equality constraints with the bad event to see if the comma syntax itself is the problem, or if it's specifically the `forall` quantifier that's causing parsing issues in the `call` tactic context.
