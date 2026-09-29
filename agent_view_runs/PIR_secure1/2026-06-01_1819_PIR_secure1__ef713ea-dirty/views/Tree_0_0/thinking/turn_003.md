# Tree-0.0 · turn 3 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:21:24.469Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline *.`

---

Good, `proc.` is committed. Now I see the procedure body with `[programs are in sync]`. The next step following the pattern from `PIR_secure2` is `inline *. wp.` to inline the `query` calls and push `wp` through the tail. Let me commit `inline *.` next.

Actually, looking at the PIR_secure2 proof pattern:
```
proc. inline *. wp.
while (={PIR.s', j}).
...
```

Let me commit `inline *.` and then `wp.`.


I could combine them as `inline *; wp.` or apply them separately—let me start with `inline *` on its own.
