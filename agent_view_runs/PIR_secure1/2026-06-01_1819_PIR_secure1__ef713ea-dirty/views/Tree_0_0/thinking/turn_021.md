# Tree-0.0 · turn 21 · commit_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:32:13.305Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: ={PIR.s}).`

---

`call (_: ={PIR.s}).` was accepted. The probe preview shows:

```
pre = s{1} = s{2} /\ PIR.s{1} = PIR.s{2}
post = big predT a s{1} = big predT a s{2} /\ PIR.s{1} = PIR.s{2}
```

This is better! The call spec now carries `={PIR.s}`. The postcondition requires `big predT a s{1} = big predT a s{2}` (trivially true from `s{1} = s{2}`) AND `PIR.s{1} = PIR.s{2}` (given in the precondition). 

So `auto` should close this, and the residual goal before the final call should only require `={PIR.s}` rather than `={PIR.s'}`. I'll apply the same call spec to both query calls, use `auto` to discharge them, then tackle the while loop.
