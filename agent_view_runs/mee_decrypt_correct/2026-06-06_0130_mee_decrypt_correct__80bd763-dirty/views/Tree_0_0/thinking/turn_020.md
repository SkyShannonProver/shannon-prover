# Tree-0.0 · turn 20 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:44:22.724Z -->

**Intent:** `probe_tactic`  
**Payload:** `while (true) (size c - i).`

---

Goal 1 of 5: The while loop with `post = true`. This is a losslessness goal — I just need to show the while loop terminates with probability 1. Since the procedure body contains a call to `PRPc.PseudoRP.fi` (which is deterministic/lossless), this should be doable.

For losslessness of a while loop, I use:
```
while (true) (size c - i).
```

This says: invariant = `true` (always holds), variant = `size c - i` (decreases each iteration).

The `while` tactic should generate:
1. A goal showing the body preserves the invariant with probability 1 while decreasing the variant
2. A goal verifying the variant is positive

I need to make sure the while loop is the last remaining instruction after the `seq` tactic, then `while (true) (size c - i).` should handle both obligations.
