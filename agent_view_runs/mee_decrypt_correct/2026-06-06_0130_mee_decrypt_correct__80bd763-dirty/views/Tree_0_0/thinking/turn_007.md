# Tree-0.0 · turn 7 · lookup_symbol

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:32:58.181Z -->

**Intent:** `lookup_symbol`  
**Payload:** `PRPc.PseudoRP.fi`

---

`hoare.` was accepted but produces a bad subgoal: `0%r = 1%r` which is false. This is because the `hoare` tactic in phoare logic tries to convert `phoare [=] 1%r` by splitting into a hoare triple plus a probability side condition. But since there are no samples in the body (it's deterministic), the probability of the body not failing is... hmm, actually the problem is that `hoare.` in EasyCrypt phoare logic generates `0%r = 1%r` which means the probability component comes from `Pr[body : true] = 0`, but the postcondition hoare part needs `Pr[body : true] >= 1`, and the remaining is `0%r = 1%r` which doesn't work.
Looking at the actual goal, I see `0%r = 1%r` which is clearly false, so `hoare.` isn't the right tactic here. The real issue is that the procedure contains calls to other procedures like `PRPc.PseudoRP.fi` and `MAC.verify`, which `hoare.` can't handle since it needs to account for their probability contributions.

I need to try a different approach — either using `conseq` to restructure the phoare goal, or stepping through the code with `sp` and `wp` while handling the procedure calls with `call` or `ecall` using appropriate specs. Let me also reconsider whether `inline` might work with the correct module path.
