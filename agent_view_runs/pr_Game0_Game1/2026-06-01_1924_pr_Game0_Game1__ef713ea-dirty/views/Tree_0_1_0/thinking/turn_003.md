# Tree-0.1.0 · turn 3 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:56:46.212Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Good, the `seq` was accepted. Now I have 3 goals (was 2, now 3 because seq splits one goal into two subgoals plus the remaining second original goal). Let me read the full view to see the first subgoal clearly.

Now I can see the first subgoal clearly. This is the prefix subgoal:

LHS (7 statements):
```
Log(LRO).init()                 (1)
kp <$ dkeys                     (2)
(pk, sk) <- kp                  (3)
(m0, m1) <@ A(Log(LRO)).a1(pk)  (4)
b <$ {0,1}                      (5)
pk0 <- pk                       (6)
m <- if b then m0 else m1       (7)


```

On the RHS, I'm looking at a simplified version with just 4 statements that removes some of the intermediate steps. The precondition requires that the adversary's global state and the log's message match between the two games, and the postcondition checks that the global state and query log remain synchronized.

Now I need to work through the postcondition that's being specified here. The key insight is that I need to trace through what happens when I inline the initialization, handle the key generation, process the oracle call, and then manage the conditional assignment of m based on the bit b. Let me map out the approach: first I'll expand the Log initialization to see what gets recorded, then handle the keygen sampling, work through the A.a1 oracle call, process the random bit, and finally handle the pk0 and m assignments on the left-hand side.

```
wp.
```

to push past the deterministic assignments at the end. On the left side, I can move past the m assignment and pk0 assignment since those are deterministic, but the b sampling is where things get interesting. On the right side, the last statement is also the b sampling, so I need to be careful about how the weakest precondition handles this divergence. nothing on the RHS. After `wp` consumes those deterministic statements, I'm left with the remaining programs on each side — the LHS still has the initial setup and sampling statements, while the RHS has a slightly different structure due to the different variable assignments. The postcondition then gets updated to incorporate the weakest precondition of those consumed assignments.

Now I need to handle the `b <$ {0,1}` sampling on both sides by coupling them with `rnd`, which will make them equivalent. After that, I'm left with the key part: the calls to `A.a1` on both sides, which I can handle by establishing that the log state and adversary input are equal. For the A.a1 call, I need `call (_: ={Log.qs, LRO.m}).` But wait, the `call` tactic for `A(Log(LRO)).a1` needs invariants for the oracle `Log(LRO).o` as well. In EasyCrypt, `call (_: P)` for a module with oracle access generates subgoals for each oracle procedure.

Hmm, for a standard call with equality, I should use:
```
call (_: ={Log.qs, LRO.m}).
```

This would generate subgoals:
1. For `Log(LRO).o`: prove `={Log.qs, LRO.m, arg} ==> ={Log.qs, LRO.m, res}`
2. Main goal: `={pk, glob A, Log.qs, LRO.m}

==> ={m0, m1, glob A, Log.qs, LRO.m}`

The oracle subgoal should be provable by `proc; inline LRO.o; wp; rnd; skip; ...` or just `sim` or `auto`.

For the keygen, the LHS samples and destructures `kp` from `dkeys`, while the RHS directly samples the pair from `dkeys`. I can use `wp` to push past the destructuring on the LHS, then couple the two sampling operations with `rnd` since they're drawing from the same distribution.

For `Log(LRO).init()` on both sides, I'll inline the initialization procedures and use `wp; skip` to finish.

Let me try a more structured tactic sequence: I'll start with `wp` to push past the initial assignments, then `rnd` to couple the random bit sampling, followed by a `call` that handles the adversary invocation while preserving the equality of the log and oracle state. After that, another `wp` and `rnd` pair should handle the key generation where the LHS destructures the pair directly while the RHS samples and destructures—since both come from the same distribution, the coupling should work. Then `inline*` expands the initialization calls, and finally `wp; skip` closes out the proof.

The issue is that the `call` tactic generates an oracle subgoal I need to discharge, and the programs aren't quite identical in structure—the LHS has extra assignments and different destructuring patterns. Maybe `sim` could work if the module calls were identical, but they're not. Let me just work through this step by step, starting with `wp` and seeing how far I can push before needing to branch on the subgoals.
