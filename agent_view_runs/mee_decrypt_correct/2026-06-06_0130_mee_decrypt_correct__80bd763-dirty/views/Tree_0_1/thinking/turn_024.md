# Tree-0.1 · turn 24 · inspect_context

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:44:09.143Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

`inline *` is rejected again. This means `PRPc.PseudoRP` is probably an abstract module — we can't inline abstract module procedures. We need to use `call` with a specification instead.

Let me check what the `call` tactic form looks like in phoare mode. In EasyCrypt, for a phoare call, I think the form is:
- `call (_: PRE_call ==> POST_call).` — this gives a spec for the called procedure

For `PRPc.PseudoRP.fi(ek, ci)`, the spec should say that the result is `AESi ek ci`. 
I'm not entirely sure if `call` in phoare mode needs to include probability information or if it defaults to 1 for deterministic procedures. I might need to use `ecall` to reference an existing phoare lemma instead. Let me look up the exact tactic forms.
