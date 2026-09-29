# Tree-0.0 · turn 12 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:28:02.400Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true).`

---

`call (_: true).` was accepted! The probe shows the goal after would be:

```
Current goal (remaining: 2)
Type variables: <none>
------------------------------------------------------------------------
&1 (left ) : {s : int list} [programs are in sync]
&2 (right) : {s : int list}
pre = s{1} = s{2} /\ true
post = big predT a s{1} = big predT a s{2} /\ true
```

This is the call spec for `PIR.query`: given `s{1} = s{2}`, we need `big predT a s{1} = big predT a s{2}`. 

The congruence rule handles this trivially and spawns two new goals, but I'm realizing this only dealt with the second call to `PIR.query`. I still need to work through the first call and everything preceding it. Let me commit this step and continue. Actually, I'm noticing the precondition refers to the local parameter `s` within the `query` procedure itself, not the global `PIR.s` that gets passed in the call `r' <@ PIR.query(PIR.s')`.

The postcondition of my overall goal requires `={PIR.s}`, so after applying `call (_: true).`, the remaining goal should preserve the equality of `PIR.s` across both sides. Since the call invariant is just `true`, it's trivially satisfied, but the postcondition handling means the remaining program must establish `PIR.s{1} = PIR.s{2}` as a residual condition before the call completes. Let me commit this and see what the preview shows.
