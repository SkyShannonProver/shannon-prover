# Tree-0.1 · turn 13 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:40:27.131Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (true).`

---

Good, the `seq 1` was committed. Now I have 5 remaining goals. The first goal is a hoare judgment for the while loop with `post = true`. This is the termination/well-formedness goal — I just need to show the while loop terminates. Since `post = true`, any terminating execution satisfies it.

For a hoare while loop with `post = true`, I can use `while (true)` as the invariant, or even simpler, just `while (0 <= i /\ i <= size c) => //.` and close with auto. Actually, since post = true, I just need to show the loop terminates. 

Since this is a hoare judgment rather than phoare, I don't need to prove termination explicitly — the postcondition being `true` means I just need to show the program doesn't get stuck. Using `true` as the invariant should work: it's trivially preserved, and the exit condition `true /\ !guard => true` holds automatically.

The tricky part is handling the function call `pi <@ PRPc.PseudoRP.fi(ek, ci)` inside the loop body, so I need to make sure that gets properly verified as well.
