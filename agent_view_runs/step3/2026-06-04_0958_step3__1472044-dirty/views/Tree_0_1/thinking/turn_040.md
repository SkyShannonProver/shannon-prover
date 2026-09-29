# Tree-0.1 · turn 40 · undo_last_step

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:34:29.602Z -->

**Intent:** `undo_last_step`  
**Payload:** `(none)`

---

The right side is now the explicit random-sampling loop. To go manual I'd also expose the left `ChaCha.enc` loop with its `RO.get` calls and prove an eager-RO + one-time-pad coupling over the `while` — i.e. re-derive `equ_cc`, which the file itself leaves `admit`-ed. That is the wrong scope and impractical blind. 

Logically, `call`/`conseq`/`transitivity` all reject `equ_cc` purely on procedure-matching (a post-adaptation failure would yield a subgoal, never a rejection), so no postcondition reshaping will help. Let me undo this diagnostic inline and try one structurally different application path I haven't: applying `equ_cc` to the **un-split** call via `seq` on the *right* only, or via `rcond`-free direct `call` after rephrasing. First restore the clean call site.
