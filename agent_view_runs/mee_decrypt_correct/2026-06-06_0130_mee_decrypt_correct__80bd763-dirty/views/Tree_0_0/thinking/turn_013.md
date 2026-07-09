# Tree-0.0 · turn 13 · probe_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:37:36.413Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline MAC.verify.`

---

Let me check the manager result to see if this inline was accepted or rejected.

All inline attempts are rejected. Let me think about why. In phoare logic in EasyCrypt, `inline` might not be supported at all. Or perhaps the procedures are abstract (functor arguments to `MEE`) and can't be inlined.

Looking at the phoare spec again:
```
phoare mee_decrypt_correct _mk _ek _c:
  [MEEt.MEE(MEEt.PRPc.PseudoRP,MEEt.MAC).dec: ...]
```

`MEE` is a functor: `MEE(E, M)` where `E` is the PRP module and `M` is the MAC module. 

The calls to `E.fi` and `M.verify` inside `MEE.dec` are abstract since they route through the functor arguments, so `inline` can't touch them. But `PRPc.PseudoRP` is concrete — it's defined in the `PRPc` theory with a known body, so theoretically `inline` should work on it. Maybe `inline` just doesn't work in phoare context at all, or I need to try something simpler like inlining just the MAC verification step.
