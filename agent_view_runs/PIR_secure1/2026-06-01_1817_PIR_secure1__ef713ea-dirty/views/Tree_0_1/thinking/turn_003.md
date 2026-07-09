# Tree-0.1 · turn 3 · commit_tactic

<!-- session b8daceea-014c-4518-8491-4e89b1e76f77 · 2026-06-02T01:19:19.965Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto.`

---

The while invariant was accepted. Now I have 2 goals:
1. The loop body preserves `={PIR.s, j}` (current goal)
2. The initial/exit conditions

For the loop body: pre is `(PIR.s{1} = PIR.s{2} /\ j{1} = j{2}) /\ j{1} < N /\ j{2} < N`, and I need to show post `PIR.s{1} = PIR.s{2} /\ j{1} = j{2}` after the loop body executes.


The loop body samples a random bit, then conditionally prepends `j` to `PIR.s` based on that bit, and increments `j`. I should try using `auto` to handle the weakest precondition computation with random sampling and conditionals, since it's designed to work with these constructs in relational proofs.
