# Tree-0.1 · turn 2 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:21:07.448Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The probe of `proc.` was accepted. I can see the procedure body after `proc.`:
- Both sides have the same structure: initialize j, s, s', then a while loop with coin flips, then two calls to `query`.
- The postcondition is `PIR.s{1} = PIR.s{2}`.

The key observation: `PIR.s` is updated identically on both sides regardless of `i`. In both branches (`j = i` and `j ≠ i`), `j` is added to `s` iff `b = true`. So with the identity coupling on `b`, `s` stays synchronized.


Now I'm sketching out the proof strategy: commit the procedure, inline the query calls, apply weakest precondition reasoning, then set up a while loop invariant maintaining equality on `s'` and `j`. I'll handle the random sampling inside the loop with appropriate tactics, and finish with automation for the initialization.

Looking at how `PIR_secure2` structures its proof, I can see the pattern uses a conditional coupling on the random bit depending on whether indices match. For `PIR_secure1` though, since `s` gets updated the same way regardless of `i`, I should be able to use a simpler identity coupling where both sides sample uniformly and get identical results.

Actually, I need to reconsider what happens after the random sampling step—EasyCrypt will need to verify that the loop invariant still holds given the postcondition of the loop body.

Let me trace through the cases systematically: when the indices match on both sides, both branches execute identically. When they differ, the key insight is that `s` ends up equal on both sides regardless of the random bit's value, since the conditional updates preserve equality.

Now I'm thinking about how to structure the proof itself—I could try running the entire tactic sequence at once, but that might be too ambitious. Let me start with just `proc.` and work through it methodically instead. to go step by step. Let me start by committing `proc.` and then work through the proof incrementally.
