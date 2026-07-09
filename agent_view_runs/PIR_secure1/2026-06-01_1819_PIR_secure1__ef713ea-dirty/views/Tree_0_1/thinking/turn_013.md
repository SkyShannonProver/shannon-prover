# Tree-0.1 · turn 13 · undo_last_step

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:27:43.561Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

Parse error. The `sim` syntax is wrong. Let me try different approaches.

Actually, let me step back and think about what approach could work here. The fundamental issue is:
1. After `proc.`, programs are in sync
2. `inline *` fails (EasyCrypt rejects it)
3. `wp` fails (no progress)
4. `sim` works but leaves `i{1} = i{2}` which is unprovable
5. `while` fails because the last instruction isn't a while loop
6. `seq` needs different syntax for synchronized programs

Let me try a completely different approach. Let me undo `proc.` and try to prove this at the module level using `conseq`.
 
Maybe I should use `conseq` to weaken the postcondition to something `sim` can handle, or try using `sim` directly and then tackle the resulting `i{1} = i{2}` side condition separately.

Actually, that equality from `true` is unprovable—the whole point is that PIR.s should be identical regardless of `i`. Let me step back and work at the module level instead. I'm trying to prove an equivalence between two runs of PIR.main where the precondition is `true` and the postcondition is that PIR.s matches. I could convert this to a probability statement using `bypr`, which would let me reason about the distribution of PIR.s values across both executions, though I'd need to handle the fact that PIR.s is list-valued rather than working directly with the probability lemmas available.

But here's the problem: the probability lemma I'd want to use relies on `Pr_PIR_s`, which is currently admitted, so I can't actually build on that without circular reasoning.

Let me check if I can work around this by looking at how `PIR_secure2` is proven — it uses a series of tactics like `proc`, `inline`, and `wp` that successfully complete the proof, which means these same tactics should work for `PIR_secure1` as well. The key question is whether `inline *` will work after `proc` in that earlier proof.

Actually, both proofs have the same structure (`equiv PIR.main ~ PIR.main`), so the tactic sequence should be identical. Maybe the issue is with how I'm applying the tactics or the session state got corrupted somehow. Let me try resetting and applying `proc`, `inline`, and `wp` all together in one go.
