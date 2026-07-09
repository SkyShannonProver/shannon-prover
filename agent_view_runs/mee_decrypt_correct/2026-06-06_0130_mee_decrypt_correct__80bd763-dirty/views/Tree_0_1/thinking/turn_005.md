# Tree-0.1 · turn 5 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:32:31.078Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline PRPc.PseudoRP.fi.`

---

Good, so for phoare, the while tactic form is:
```
while (INVARIANT) (VARIANT).
```

Now let me plan the proof strategy:

1. First, I need to push past the suffix after the while loop. The pattern is: `wp` from the end to absorb the post-loop code (the if, MAC verify, etc.), then handle the while loop, then `sp` or `wp` to handle the initial assignments.

Actually, let me think about this differently. The typical structure for a phoare deterministic proof is:

The procedure has:
- Initial assignments (lines 1-6)
- While loop (line 7)
- Post-loop code (lines 8-9, including a call to MAC.verify)

I need to handle the calls inside the loop body and in the if-branch. In phoare mode, procedure calls need to be inlined or handled with `call`. Let me consider inlining the PRPc.PseudoRP.fi call inside the loop and the MAC.verify call separately, or maybe I should start with `sp` to push through the assignments, then `wp` to work backwards from the end.

The challenge is that `wp` can only go up to the first call site—the MAC.verify call at line 9.2—so I need to figure out the right order of tactics to handle the assignments, the loop with its invariant and variant, and the procedure calls.
