# Tree-0.1 · turn 4 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:21:41.572Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline *.`

---

The `inline *; wp.` probe was rejected. Let me try a different approach. The programs are "in sync", meaning EasyCrypt is showing them as a single column. Let me try `inline *.` alone first, then `wp.` separately, or try a different approach.

Actually, looking at `PIR_secure2`, the proof uses:
```
proc. inline *. wp.
while (={PIR.s', j}).
...
```

Let me try `inline *.` alone.

Actually wait - looking at the error more carefully, it says "Daemon probe accepted this tactic but predicted no progress; committing would be auto-reverted." That's odd. Let me try just `inline *.` by itself.


The `query` calls are at the end, and the postcondition `={PIR.s}` is already satisfied after the while loop since `PIR.s` doesn't get modified by those calls. I should try using `inline *.` to inline the `query` calls directly in the pRHL proof.
