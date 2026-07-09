# Tree-0.0 · turn 4 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:21:58.041Z -->

**Intent:** `probe_tactic`  
**Payload:** `sim.`

---

`inline *` was rejected. That's because `PIR.query` is already inlined (or maybe it's a concrete procedure and EasyCrypt's `inline` doesn't work with it in this context). Let me try `wp.` to push through the tail (the `query` calls and return), or try `sim.` or approach it differently.

Actually, looking at the PIR_secure2 proof again:
```
proc. inline *. wp.
```

But here, `inline *` was rejected. Let me think about why. Maybe the programs are "in sync" and EasyCrypt treats them differently. 

Since `query` is defined as a concrete module procedure, `inline *` should theoretically work unless the synchronized programs require a different approach. Let me try `inline PIR.query.` explicitly or just use `wp.` to see if that can handle the procedure calls directly. proc.`, maybe EasyCrypt already inlined? Let me try just `wp.` to push through the deterministic tail.

Actually, let me re-read the program structure. After `proc.`, we see:
```
(4------)  r <@ PIR.query(PIR.s)
(5------)  r' <@ PIR.query(PIR.s')
```

These are call sites. `inline *` should inline them. But it was rejected. Maybe I should try `inline PIR.query.` specifically, or `inline{1} PIR.query; inline{2} PIR.query.`

Actually, wait. Looking at the error more carefully: "EasyCrypt rejected the committed tactic." So inline * was simply rejected. Maybe because the programs are in sync and you need to specify sides? Or maybe inline * doesn't work in pRHL when the programs are synced?

Let me try a different approach. Instead of inlining, I'll work with the structure as-is. The PIR_secure2 proof used `proc. inline *. wp.` successfully, so `inline *` should work here too. Maybe the issue is that the programs are already in sync and there's nothing to inline, or perhaps I should just try `wp.` directly to handle the return and query calls. Since `PIR.s` doesn't depend on `i`, I could also try using a while loop invariant that keeps those values synchronized. Since `PIR.query` is a procedure call rather than a deterministic operation, I can't use `wp` to reason through it directly—I'll need to use `inline` or `call` tactics instead. Let me try `sim` first to see if EasyCrypt can automatically handle the equality relation, since `PIR.s` remains unchanged after both query calls and the postcondition only depends on the state after the while loop.
