# Tree-0.1 · turn 7 · undo_to_checkpoint

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:41:53.232Z -->

**Intent:** `undo_to_checkpoint`  
**Payload:** `(none)`

---

Good, undo was successful. I'm back to the state after `proc` and `inline BR93(LRO).keygen BR93(LRO).enc.`

Let me think about the "upto bad" call syntax more carefully. Maybe the issue is that EasyCrypt uses a different syntax. Let me try:

1. `call (_: inv) bad.` (bad event after the invariant, as a separate argument)
2. Or maybe I need to use `wp` first and then `call`

Actually, wait. Let me re-read EasyCrypt's documentation on the `call` tactic for "upto bad" reasoning.
 
I'm recalling the different call syntax variants in EasyCrypt — there's the standard relational form, the one-sided variants, and the explicit pre/postcondition form. But maybe I'm overcomplicating this. Let me try a different strategy: instead of wrestling with the "upto bad" call syntax, I could align the oracle states before the `a2` call happens, which might make the proof simpler overall.

The challenge is that after encryption on the left side, `LRO.m{1}` has an extra entry that `LRO.m{2}` doesn't have. I could try using one-sided sampling on side 2 to match it, but that won't work since the code is fixed and I can't inject arbitrary operations into side 2.

Let me pivot entirely and try using `byequiv` with a different postcondition — instead of `={res} \/ bad`, what if I use `(!bad{2} => ={res})`? These should be semantically equivalent, so it shouldn't actually change the proof's difficulty, but maybe the different formulation will help me see a clearer path forward.

Actually, I'm realizing the postcondition swap doesn't really solve the underlying issue with how `byequiv` handles the probability bound. Let me step back and try something completely different — maybe I should introduce an intermediate game using `have` to break down the proof into more manageable pieces. or use probability arithmetic. Let me try a different approach where I use `byequiv` with a simulation that handles the module override automatically. Looking back at Game1's definition with the `with` override syntax, EasyCrypt might have built-in support for reasoning about these module overrides without needing to inline everything. Maybe the key is preserving the module structure rather than expanding the keygen and encryption procedures. I need to step back and try a more direct approach. Let me undo the inline tactic and instead use `seq` to align the common prefix steps across both games—the initialization, key generation, and first adversary call should match on both sides. Then I can handle the diverging parts separately by counting out exactly which steps need to align: the LHS has 6 steps before the second call, while the RHS has 8 because of the extra random sampling and assignment steps.

Actually, maybe I should abandon this tactic entirely and try using `smt()` or `auto` to see if the solver can handle the equivalence directly without manually choreographing every step.
