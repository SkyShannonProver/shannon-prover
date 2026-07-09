# Tree-0.0 · turn 9 · inspect_context

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:33:52.794Z -->

**Intent:** `inspect_context`  
**Payload:** `tactic_forms`

---

OK. The inline procedure names need to match the concrete module names, not the abstract ones. The procedure `MEEt.MEE(MEEt.PRPc.PseudoRP, MEEt.MAC).dec` is where the call is. Inside, `pi <@ PRPc.PseudoRP.fi(ek, ci)` is a call to the functor argument. The modules `PRPc.PseudoRP` and `MAC` are module arguments to `MEE`.

In EasyCrypt, when we have `MEE(PRPc.PseudoRP, MAC).dec`, the procedure body references the functored module arguments. 

So `PRPc.PseudoRP.fi` is the PRP inverse procedure. I need to look at what `PseudoRP` actually implements and understand how it's cloned from the MAC_then_Pad_then_CBC theory. Rather than using `inline` with abstract procedure names, I should use `call` with the appropriate spec for phoare goals that reference concrete modules like `PRPc.PseudoRP`.

Looking at the clone mapping, `Pi` gets mapped to `AESi`, so `PseudoRP.fi` is essentially a wrapper that just applies `AESi` to the key and input. For the `call` tactic inside the loop, I need to figure out the right syntax in phoare logic to invoke this procedure with the correct specification.

The issue is that `inline` won't work here since `PRPc.PseudoRP.fi` is a concrete module instance rather than an inlinable procedure. I need to use the `call` tactic instead and find the right form to handle it in this context.
