# Tree-0.1 · turn 2 · commit_tactic

<!-- session b8daceea-014c-4518-8491-4e89b1e76f77 · 2026-06-02T01:19:08.898Z -->

**Intent:** `commit_tactic`  
**Payload:** `while (={PIR.s, j}).`

---

Good, the tactic was accepted. Now I can see the goal has the while loop with the relational program. Let me read the full view to see the complete goal.

Now I can see the full goal. The programs are in sync. The pre is `true` and the post is `PIR.s{1} = PIR.s{2}`.

I need to handle:
1. `j <- 0` (assignment)
2. `(PIR.s, PIR.s') <- ([], [])` (assignment)
3. A while loop with body that samples `b` and updates `PIR.s` and `PIR.s'`

The key observation: `PIR.s` gets `j :: PIR.s` when `b` is true, regardless of whether `j = i` or not. So with the identity coupling on `b`, `PIR.s` evolves identically on both sides.


I'll use a while loop invariant asserting that `PIR.s` and `j` are equal on both sides throughout execution. This means I need to verify the loop body maintains this equality, the initial assignments establish it, and the invariant at loop exit gives me the postcondition.
