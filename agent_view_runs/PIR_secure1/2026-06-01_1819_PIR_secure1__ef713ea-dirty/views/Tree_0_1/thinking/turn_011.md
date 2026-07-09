# Tree-0.1 · turn 11 · commit_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:26:46.320Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

OK, the call tactic forms say:
- Form 1: `call LEMMA.` — use when an equiv lemma already proves the procedure correspondence
- Form 2: `call (_: INVARIANT).` — use when you need to provide the oracle invariant manually

For the `query` calls which are concrete module procedures (not abstract adversaries), the `call` tactic works differently. For concrete procedures, you don't use `call (_: inv)` — that's for abstract adversary calls.

For concrete procedure calls, the standard approach in EasyCrypt is:
1. `inline PIR.query.` to inline the call


2. Then `wp.` to absorb the assignments

But `inline PIR.query.` was rejected while `inline *.` was accepted but made no progress. The fact that the wildcard form is accepted but produces no progress, while the specific procedure name is rejected, suggests the `query` procedure might have already been inlined internally by EasyCrypt.

Looking at the goal display though, I still see `r <@ PIR.query(PIR.s)` and `r' <@ PIR.query(PIR.s')`, so they're definitely not inlined. Let me try using `conseq` to weaken the postcondition and split the proof differently, though I'm running into issues with what conditions I actually need to establish. Maybe I should step back and reconsider this approach entirely.

Actually, let me try `sim` with an explicit relation argument like `sim (_: ={PIR.s}).` — the `sim` tactic can take a postcondition to guide the proof, which might avoid the problem where it tries to prove more than necessary and then demands `i{1} = i{2}` as a side condition.

Wait, I'm realizing the real issue: `PIR_s_uniform` has the precondition `={i}`, but our goal needs a different precondition, so I can't directly apply it.

Let me step back and think about what the proof should actually do. The core idea is showing that `PIR.s` gets the same distribution regardless of the input `i`. The natural proof strategy would be to enter the procedure, handle the query calls somehow, set up a while loop that maintains the invariant that `PIR.s` and the loop counter stay synchronized between the two executions, then use random sampling with identity coupling on the random bits, and finally close out the initialization.

The main obstacle is getting past those query calls—neither `inline *` nor `wp` seem to work, so maybe I need to use `call` to handle the concrete procedures directly.

Actually, I'm realizing that `call` in EasyCrypt's pRHL is meant for abstract adversary calls where you provide an oracle invariant, not for concrete procedure calls like these. For concrete modules, the standard approach is to `inline` the call to expose its body, then use `wp` to process the resulting assignments.

The fact that `inline *` isn't making progress is strange. Let me try `inline{1}` to inline only on the left side, though I'm not sure if that works with synchronized programs. Or maybe I should use `sp` to step through the first couple assignments and get to the while loop, then tackle that. But I'm stuck on the fundamental issue that the inputs are genuinely different — `i{1} = i{2}` can't be proven from `true`. Let me try using `conseq` to set up a more realistic postcondition...

Actually, wait. I already have `PIR_security_s_bypr` which proves something related to the probability distribution of `PIR.s`. Maybe I can leverage that existing result instead of trying to force the equivalence proof through. I see that `Pr_PIR_s` establishes the probability is independent of the index, so I could use that to derive `PIR_secure1` via the `bypr` tactic. The tactic converts an equivalence into a probability statement, requiring me to show that for any predicate on the shared state, the probabilities match between the two sides—which should follow directly from the fact that the probability doesn't depend on which index was used. I see the issue now — the programs are synchronized after `proc.`, which prevents me from using relational tactics effectively since they're showing as identical code in a single column. But the proof actually needs to handle different inputs `i` and show that the output `PIR.s` remains the same despite the different couplings on random sampling. I need to step back and work at the module level before `proc.` to force EasyCrypt to treat the programs as unsynchronized so I can apply different couplings.

Looking at how `PIR_secure2` successfully uses `proc. inline *. wp.` to work through the loop invariant, I'm wondering why the same approach isn't working for `PIR_secure1` — maybe that proof was already completed in the file and I'm missing something about the current state. (it's not admitted), and EasyCrypt processes the file sequentially. So maybe `inline *` works in `PIR_secure2` but not in `PIR_secure1` because of some ordering issue? That doesn't make sense.

Actually, looking at the file again, `PIR_secure1` comes BEFORE `PIR_secure2`. Both are equivs of `PIR.main ~ PIR.main`. `PIR_secure2` proves `={PIR.s'}` and its proof uses `proc. inline *. wp.` followed by `while`. So the same approach should work for `PIR_secure1`.

Maybe the issue is that the manager is incorrectly blocking these tactics. Let me try to commit `inline *.` directly despite the manager's "no progress" prediction.

The manager said it would auto-revert, but that's just a prediction—maybe it's wrong. Let me try committing `inline *.` anyway and see what actually happens.
