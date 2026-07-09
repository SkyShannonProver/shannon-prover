# Tree-0.1 · turn 23 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:43:53.576Z -->

**Intent:** `probe_tactic`  
**Payload:** `inline *.`

---

Let me check if the inline was accepted or rejected.

`inline PRPc.PseudoRP.fi.` is still rejected. Let me try different inline syntax. Maybe the module path is different. Let me try:
- `inline PseudoRP.fi.`
- `inline{1} PRPc.PseudoRP.fi.`
- `inline *.` (might work at this level)
- `inline (2).` (to inline at statement 2)

Let me try a few of these.

Actually, maybe the issue is that `PRPc.PseudoRP` is an abstract module in this context, not a concrete one. If it's abstract, we can't inline it — we can only use `call` with a spec.
Looking at the MEEt clone, `PRPc` comes from `MAC_then_Pad_then_CBC.PRPc`, and `PseudoRP` is likely a wrapper module around the PRP operations similar to what's defined in EasyCrypt's standard PRP theory.

Since the clone binds `P <- AES` and `Pi <- AESi`, the path `PRPc.PseudoRP.fi` should resolve to `AESi k x`. I'm trying `inline{1} PRPc.PseudoRP.fi` for the phoare case, though in phoare mode with only one side, the `{1}` might not be necessary. Let me experiment with `inline *.` to see if that works better here.
