# Tree-0.1 · turn 16 · probe_tactic

<!-- session 8c4e4f6f-af9c-42e3-beaa-964d13603474 · 2026-06-02T01:29:37.283Z -->

**Intent:** `probe_tactic`  
**Payload:** `bypr (PIR.s{1}) (PIR.s{2}).`

---

Good, I'm back at the module-level goal:
```
pre = true
PIR.main ~ PIR.main
post = PIR.s{1} = PIR.s{2}
```

Now let me think about a different approach. The `proc` approach had issues with synchronized programs. Let me try `byequiv` or a different proof technique.

Wait, I'm already in an equiv proof. `byequiv` is used to go FROM a probability statement TO an equiv.

What about using `transitivity`? I could prove `PIR.main ~ PIR.main : true ==> ={PIR.s}` by using an intermediate game that uses a fixed `i` value.


Actually, the core issue keeps coming back to this: `PIR.s` gets updated the same way no matter what `i` is. Every branch adds `j` to `PIR.s` exactly when `b = true`, so the final state should be identical. The proof structure should mirror `PIR_secure2`, but that one uses `proc. inline *. wp.` which gets rejected for synchronized programs. Let me double-check if `PIR_secure2`'s proof actually works...

Hmm, if `inline *` doesn't work for `PIR_secure1` (they're both comparing `PIR.main ~ PIR.main`), then why does `PIR_secure2`'s proof compile? The difference might be file ordering—`PIR_secure1` comes first and gets `admit`ted, so EasyCrypt skips past it and processes `PIR_secure2` next. But that shouldn't affect whether `inline *` is valid syntax...

Actually, the real problem might be that when I enter the `PIR_secure1` proof, `proc.` puts the programs in sync, and then `inline *` fails. But `PIR_secure2` has the exact same module pair, so why would `inline *` work there? Either the file was modified and `PIR_secure2` was verified with a different EasyCrypt version, or the "programs in sync" state is actually fine for `inline *` in the original but the session manager is incorrectly blocking it.

Let me try a different tactic using `bypr` at the module level instead.

Actually, I need to understand `bypr` better — it's used to convert an equivalence into probability statements. The tactic takes two boolean expressions and transforms the equivalence goal into statements about probability equality across the two programs. I'm checking what `bypr` generates for our postcondition `={PIR.s}`, which expands to `PIR.s{1} = PIR.s{2}`. The issue is that we have `Pr_PIR_s` proved for the fset-valued `oflist PIR.s`, but not directly for the list-valued `PIR.s`. Let me try strengthening the postcondition with `conseq` to require all local variables and globals to be equal, then use `sim` to close it—though this might still leave `i{1} = i{2}` unresolved since `i` isn't included in the strengthened postcondition. I'm exploring whether the `proc` tactic can help here. I'm realizing that `while` won't work here because it requires the while loop to be the final instruction, but the calls to `query` come after it. I need a different approach—maybe using `sp` to step through the initial assignments and then handle the remaining structure, or finding a tactic that can work with instructions that aren't strictly synchronized at the end. ens post.

I'm realizing I need to split the proof at the while loop boundary using `seq`, but that's causing syntax issues with synchronized programs. Let me try a different approach — maybe I can use `sp` to absorb the assignments first, then apply `seq` to isolate the loop.

Actually, I'm overcomplicating this. Since `PIR.s` is independent of the loop variable `i` and only depends on whether `b` is true, the two programs should be functionally equivalent for that state. Let me try reducing this with `bypr` instead.

Testing `bypr` form...
