# Tree-0.1 · turn 6 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:22:21.889Z -->

**Intent:** `probe_tactic`  
**Payload:** `sim.`

---

OK, `wp.` also rejected (same "no progress" issue). The programs are "in sync" so EasyCrypt treats them as identical. In that case, `wp`, `inline`, etc. have nothing to do because they would produce the same goal.

Since the programs are fully synchronized, `sim` should work. The `sim` tactic in EasyCrypt tries to prove that two programs produce the same result by showing they are syntactically similar. Since the postcondition is `={PIR.s}` (just one global variable), and the programs are identical (just with different local `i` values), `sim` should be able to handle this.
 
But wait—`sim` needs to preserve the relation between the two sides, and here the `i` values differ in the precondition. The tactic would need to show that `PIR.s` remains unaffected by the different `i` values, which is actually the crux of what we're trying to prove. The problem is that program execution branches on `j = i`, so even though `PIR.s` ends up identical, the paths taken are different. I need to find a tactic that can handle this divergence while still proving the postcondition holds.

Let me try establishing a loop invariant with `while (={PIR.s, j})` to keep those variables synchronized, then handle the loop body. Before that, I should absorb the setup statements first. I'm going to attempt the full proof strategy: establish the invariant, apply weakest precondition reasoning, handle the randomness, and let automation finish the details.

Actually, let me just try `sim` directly since the programs are identical—it might handle the postcondition `={PIR.s}` without needing extra annotations.
