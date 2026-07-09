# Tree-0.1 · turn 22 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:32:42.804Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc; inline *; wp.`

---

Now I have the new equiv goal:
```
pre = arg{2} = arg{2} /\ arg{1} = arg{1}   (which is true)
PIR.main ~ PIR.main
post = PIR.s{1} = a <=> PIR.s{2} = a
```

This is essentially the same structure but with a weaker postcondition. The candidate moves suggest `proc; inline *; auto.` — let me try that! The `proc; inline *; auto.` might work now because the precondition has `arg{1}` and `arg{2}` explicitly (not `true`), which might prevent EasyCrypt from synchronizing.


Let me test `proc; inline *; wp.` to see if the inlining actually takes effect this time.
