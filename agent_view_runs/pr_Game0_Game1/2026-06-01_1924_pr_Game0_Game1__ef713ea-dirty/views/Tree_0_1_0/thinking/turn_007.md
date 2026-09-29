# Tree-0.1.0 · turn 7 · commit_tactic

<!-- session 1a85e7aa-e3cb-4466-a034-9c782f2d2105 · 2026-06-02T02:57:35.971Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline*; wp; rnd; skip; auto.`

---

The oracle subgoal is closed. Now I'm back to the prefix subgoal after the `call`. The remaining programs are:

LHS:
1. Log(LRO).init()
2. kp <$ dkeys
3. (pk, sk) <- kp

RHS:
1. Log(LRO).init()
2. (pk, sk) <$ dkeys

The postcondition includes `pk{1} = pk{2} /\ ={glob A, Log.qs, LRO.m}` and some forall quantifier from the `call` and `rnd` (the quantified obligations from earlier).


I need to handle the init, keygen, and destructuring steps. I'm thinking about inlining the init calls, then using weakest precondition to push past the destructuring, coupling the samplings with a random tactic, and finishing with skip and automation to discharge the pure obligation.

Now I'm working through what happens after inlining. The left-hand side has the keygen sample followed by destructuring, while the right-hand side destructures directly from the key generation. When I apply weakest precondition, it absorbs the deterministic destructuring on the left but stops at the sample, leaving me with the keygen sample on both sides but in different positions—the left still has the intermediate binding while the right has already destructured.

To couple these, I need to handle the fact that they're sampling from the same distribution but with different destructuring patterns. The `rnd` tactic should be able to couple them since they're both drawing from `dkeys`, treating the identity function as the coupling. After that, the remaining assignments are just the initialization, which should fall through with automation.
