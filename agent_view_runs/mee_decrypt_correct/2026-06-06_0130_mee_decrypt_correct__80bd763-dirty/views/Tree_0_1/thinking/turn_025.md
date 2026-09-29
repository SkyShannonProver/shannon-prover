# Tree-0.1 · turn 25 · probe_tactic

<!-- session c734b5f7-6302-4dd6-995d-5d723e5ab4e5 · 2026-06-06T08:44:37.896Z -->

**Intent:** `probe_tactic`  
**Payload:** `wp.`

---

The call tactic forms shown are for pRHL/equiv mode (two-sided). For phoare (one-sided), the call form might be different.

In EasyCrypt's phoare logic, the call tactic form is:
- `call (_: PRE ==> POST).` where PRE is the precondition for the call and POST relates the result to the inputs.

For `PRPc.PseudoRP.fi(ek, ci)`, which returns `AESi ek ci`, the spec should be:
- `call (_: true ==> res = AESi arg.`1 arg.`2).` — but I'm not sure about the argument syntax.
Actually, in phoare mode, `call` might use a different form with a time annotation, or I might need to use `ecall` to reference an existing phoare lemma. But even a simple `call (_: true)` would preserve the trivial precondition while losing the relationship between the inputs and the result. I need to think through how to properly capture that connection.

Maybe I should try using `wp` to push backward past the call, since some EasyCrypt versions can handle procedure calls that way by reasoning about their return values. Or the issue could be that `inline` fails because the phoare body after the while decomposition isn't presented as a module-level definition. Let me try a sequence: first `wp` to push past the deterministic assignments, then see what's left at the call site.
