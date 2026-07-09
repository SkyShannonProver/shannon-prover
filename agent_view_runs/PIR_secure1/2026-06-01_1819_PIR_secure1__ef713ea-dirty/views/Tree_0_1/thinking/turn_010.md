# Tree-0.1 · turn 10 · inspect_context

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:25:26.836Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

The error says "seq onsided: a pre and a post is expected". The `seq` tactic in EasyCrypt pRHL requires both pre and post when the programs are one-sided/synchronized. The syntax needs two indices for the two sides: `seq 3 3: (={PIR.s}).`

Let me try that.

Actually wait, looking at the error message more carefully: "seq onsided: a pre and a post is expected". This sounds like it needs `seq N: (<pre>) (<post>).` syntax for one-sided programs. But that doesn't make sense for a two-sided `seq`.


I'm reconsidering the `seq` syntax in EasyCrypt — maybe I need to specify both sides explicitly with `seq 3 3: (={PIR.s}).` to handle synchronized programs. But I'm also wondering if I should step back and try a completely different approach at the module level instead of using `proc.`

Looking at the available options, I could use `byequiv` to convert to a `Pr` statement, apply `conseq` at the module level to strengthen the result, or directly leverage `PIR_s_uniform` which establishes that PIR.s has a uniform distribution. Since `PIR_secure1` already states that the output distribution of `PIR.s` is identical regardless of input, using `PIR_s_uniform` seems like the most direct path forward.

The lemma establishes that for any two valid subsets, the probability of getting one equals the probability of getting the other, which demonstrates uniformity over `oflist PIR.s`. However, this requires `={i}` as a precondition, and our current goal only has `true`, so I need to find a way to either weaken the lemma or adjust my approach.

Let me step back and reconsider. Using `sim` after `proc` would leave me with the goal `forall &1 &2, true => i{1} = i{2}`, which is unprovable since the inputs can differ. The real issue is that `sim` couples everything with identity, but `i` legitimately varies between the two executions. What I actually need is a non-trivial coupling strategy for `b` inside the loop that doesn't force `i` to be equal.

Let me go back to working with the `while` loop directly—the earlier attempt failed with an "invalid last instruction" error, so I need to debug that approach.
