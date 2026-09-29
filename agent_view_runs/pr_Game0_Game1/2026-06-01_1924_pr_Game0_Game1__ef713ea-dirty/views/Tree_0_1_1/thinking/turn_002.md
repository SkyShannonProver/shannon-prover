# Tree-0.1.1 · turn 2 · commit_tactic

<!-- session db364dba-374a-4d5e-a03e-0f24d9575646 · 2026-06-02T03:03:52.346Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd.`

---

The `seq` cut was accepted. Now I have 3 remaining goals (was 2, the seq created 2 new subgoals replacing 1). Let me read the full workspace view to see the current goal.

Good. The first subgoal is the prefix: prove that after executing 5 statements on the left and 4 on the right, the invariant `={glob A, glob LRO, glob Log, pk, sk, m0, m1, b}` holds.

The code is:
LHS: init, kp <$ dkeys, (pk,sk) <- kp, A.a1(pk), b <$ {0,1}
RHS: init, (pk,sk) <$ dkeys, A.a1(pk), b <$ {0,1}


These are semantically equivalent. I'll work backwards from the final sampling statement, coupling the random bit generation on both sides, then handle the A.a1 call with its oracle equivalence obligation, and finally deal with initialization and key sampling through inlining and weakest precondition reasoning.

Looking at the structure from the end: both sides sample `b` uniformly, then both call `A(Log(LRO)).a1(pk)` with the same arguments, and before that they initialize the log and sample keys—though the RHS combines key sampling into a single operation while the LHS does it in steps.

For the `call` tactic in pRHL, I need to establish the right invariant. The precondition requires that the adversary's state, the LRO global, and the Log global are all synchronized between the two sides before the call happens.

The oracle invariant `={glob LRO, glob Log}` should work here since the oracle behaves identically on both sides, and this invariant is maintained through each oracle query. The postcondition would then give us equality of the adversary's output and all global state. I need to verify that the postcondition after the random coupling and the oracle call actually establishes the equality I need across all the global state. Let me work through the proof strategy: first coupling the random bit, then making the oracle call with the invariant that keeps the LRO and Log state synchronized, and finally checking that the initial setup with keygen produces the full equality I'm after. I need to apply the `rnd.` tactic to couple the final random samplings of `b` on both sides, which should work directly since they're drawing from the same distribution. After this step, the postcondition will drop the `b{1} = b{2}` equality and leave me with 4 statements on the left versus 3 on the right to prove equivalent.
