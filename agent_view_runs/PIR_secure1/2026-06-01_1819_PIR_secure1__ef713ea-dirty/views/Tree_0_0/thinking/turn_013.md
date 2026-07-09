# Tree-0.0 · turn 13 · probe_tactic

<!-- session b18fd1bc-4521-4ef4-bac6-acb174409c15 · 2026-06-02T01:28:17.213Z -->

**Intent:** `probe_tactic`  
**Payload:** `auto.`

---

Now I have 2 remaining goals. The current goal (first of 2) is:

```
pre = s{1} = s{2} /\ true
post = big predT a s{1} = big predT a s{2} /\ true
```

This is the call spec for `PIR.query`. Since `s{1} = s{2}`, we get `big predT a s{1} = big predT a s{2}`. This should be closable with `skip; smt().` or just `auto.` or `sim.` or `skip => />`.


Let me try `auto.` first since this is a pure pRHL goal with no program body — just the precondition implying the postcondition. The program columns are empty, so `skip.` should discharge the trivial empty program and leave a pure goal that the SMT solver can handle.
