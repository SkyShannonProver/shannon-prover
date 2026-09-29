# Tree-0.0 · turn 22 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:32:23.238Z -->

**Intent:** `commit_tactic`  
**Payload:** `auto.`

---

The call spec goal (goal 1 of 2) is:
```
pre = s{1} = s{2} /\ PIR.s{1} = PIR.s{2}
post = big predT a s{1} = big predT a s{2} /\ PIR.s{1} = PIR.s{2}
```

This is trivially true: from `s{1} = s{2}`, we get `big predT a s{1} = big predT a s{2}`, and `PIR.s` is unchanged. Let me close this with `auto.` and then do the same for the second call.


Now I'll apply the same tactic to both calls by using `auto.` to discharge the first one, then setting up the second call with the PIR state equality constraint and using `auto.` again.
