# Tree-0.1 · turn 4 · inspect_context

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:32:12.291Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

The probe of `inline *` seems to have been accepted but the goal shown is "unchanged" — let me read the full view to see the result of the probe.

`inline *` was rejected. That's because in phoare mode, `inline *` might not work the same way. Let me try a different approach.

Looking at the procedure body:
- Lines 1-6: deterministic assignments
- Line 7: while loop with a call to `PRPc.PseudoRP.fi` inside
- Lines 8-9: unpad + if/MAC verify

For a phoare proof, the standard approach would be:
1. `sp` to consume the initial assignments
2. Use `wp` to push past some suffix
3. Handle the while loop with invariant
4. Deal with the call inside the loop using the `call` tactic

Let me start by pushing past those first six assignments with `sp`, then figure out how to handle the while loop in a phoare context.
