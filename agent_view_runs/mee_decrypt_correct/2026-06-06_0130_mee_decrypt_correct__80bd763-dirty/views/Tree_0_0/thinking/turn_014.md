# Tree-0.0 · turn 14 · commit_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:39:04.546Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

Also rejected. Let me check the workspace view to confirm. Actually, let me read the source of the MAC_then_Pad_then_CBC theory to understand the module structure. Let me search for this file.

Actually wait, I should look at how the mee_encrypt_correct phoare was expected to be proved. Both encrypt and decrypt phoare specs are admitted. They're both phoare `= 1%r` with procedure calls.

Let me think differently. Maybe I should try `conseq` to separate this into useful pieces. The key insight is that the phoare `[=] 1%r` can be split via `conseq` into:
1. A hoare part (the postcondition always holds)
2. A probability part (the procedure terminates with probability 1)

The `hoare.` tactic failed because it doesn't properly decompose `[=]` bounds. But `conseq` might let me specify the decomposition explicitly. I need to figure out the right form for `conseq` with phoare—it takes a different structure than I initially tried.

Writing phoare decomposition...

Actually, I'm not confident about the exact `conseq` syntax for phoare, so let me consider a different angle. Maybe `ecall` could help handle the procedure calls, since it's designed to apply phoare specs to calls, but the nested structure inside the loop and conditional makes that tricky to apply directly.

Let me reconsider why `inline` isn't working. The procedure uses functor parameters like `PRPc.PseudoRP` and `MAC`, and the calls inside go through those parameter paths. EasyCrypt typically can't inline functor-parameter calls because the body is abstract. But wait — `PRPc.PseudoRP` is actually concrete here. When we instantiate `MEE(PRPc.PseudoRP, MAC)`, we're applying the functor to concrete arguments, so `inline` should theoretically be able to resolve them...

Unless the issue is that EasyCrypt's `inline` tactic doesn't support inlining in phoare context at all. That would explain why every `inline` attempt fails regardless of what I'm trying to inline. Let me try applying `inline` after `sp.` to see if it works on a different proof state, or maybe I should look at the actual MEE module structure in the source to understand what's happening.

Let me look at the `MEE.dec` procedure and the `PseudoRP`/`MAC` module definitions more carefully.

Now I understand the structure:

1. `PseudoRP` is a module type (from the `PRP` library), not a concrete module. The clone `clone import PseudoRP as PRPc` with the ops creates a concrete module.

2. `MEE(P : PseudoRP)(M : MAC_Scheme)` is a functor. Inside `MEE.dec`:
   - `pi <@ P.fi(ek, ci)` — calls the functor parameter `P`'s `fi` method
   - `b <@ M.verify(mk, p', t)` — calls the functor parameter `M`'s `verify` method

3. In the phoare spec, `MEE(PRPc.PseudoRP, MAC).dec` instantiates the functor with `P = PRPc.PseudoRP` (the concrete PRP module from the clone) and `M = MAC` (the concrete MAC module defined at line 73).

4. `PRPc.PseudoRP` is a concrete module wrapping the ops `P`/`Pi`, which are mapped to `AES`.

The `PseudoRP` module provides keygen, f, and fi procedures — keygen generates a random key, while f and fi apply the forward and inverse operations respectively. Similarly, `MAC.verify` checks if the computed MAC matches the provided tag. Both are deterministic one-statement returns, so `PRPc.PseudoRP.fi(ek, ci)` simply applies the inverse AES operation.

The issue with `inline` seems to be context-dependent — it works in some proof contexts but fails in phoare, possibly because the tactic doesn't recognize the module path or the phoare context has different scoping rules for inlining concrete procedures. reason. Let me try a different approach instead—maybe using `ecall` or `call` with a hoare spec would work better. In phoare context, I can apply `call` with a pre/post condition pair when there's a hoare spec available for the procedure. For `PRPc.PseudoRP.fi`, I'd need to set up a spec that captures the relationship between inputs and outputs, then use that to discharge the call obligation.

But I need to be careful about positioning—`call` works on the last call in the remaining code, so I'd need to process the code strategically, absorbing the deterministic parts with `wp`, handling the call, then dealing with the loop and conditional blocks in the right order.

The issue is that `wp` can't cross the `if` block because it contains a call to `MAC.verify`. So I need to work backwards from that call, handling the deterministic suffix first, then the call itself, then figure out how to handle the loop and the conditional structure that wraps everything.

My approach is to use `seq` to split the proof at strategic points—after the while loop completes and `padded` is established, then handle the suffix with the `unpad`, the conditional check, and the verification call separately. For the while loop itself, I'll need an appropriate loop invariant. But I'm still working through how to properly handle the calls in the conditional block.

Let me start simple: commit `sp.` to process the prefix, then try `wp.` to see how far it can work backward from the end.
