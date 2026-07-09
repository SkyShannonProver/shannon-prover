# Tree-0.0 · turn 19 · commit_tactic

<!-- session f93450d3-902b-4994-a8d4-2e9696201726 · 2026-06-06T08:44:05.772Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 : (padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\ ek = _ek /\ mk = _mk /\ p = None).`

---

"invalid last instruction" — the `while` tactic can only be applied when the LAST instruction in the remaining code is a while loop. But after `sp.`, the remaining code has:
1. while loop
2. pt <- unpad padded
3. if block

So the last instruction is the `if` block, not the while loop. That's why `while` gives "invalid last instruction."

I need to process the code from the END first (using `wp` or `call` to remove the suffix), or use `seq` to split at the while loop boundary.

OK so the `seq` approach is the right one. 

Let me apply `seq` and work through the resulting goals. The `seq` tactic should decompose this into multiple subgoals — likely a hoare goal for the while loop establishing an intermediate predicate, some probability side conditions, and then the continuation with the remaining instructions. The first goal has `post = true` which might be checking losslessness for the while loop, so that should be manageable.

Before committing though, I'm wondering if 5 goals is too many and whether there's a simpler approach. Maybe I should undo `seq` and try something different. The standard EasyCrypt phoare proof pattern I've used before is `proc`, then inlining procedure calls, `wp`, handling loops with `while`, and finishing with `skip; smt`. But since `inline` doesn't work in phoare contexts, I need to find an alternative. Actually, let me double-check whether `inline` really fails in phoare or if the issue is something else — maybe the procedure names or module references are the problem.

Looking at how the MEE functor instantiates with concrete modules, when I write `MEE(PRPc.PseudoRP, MAC).dec`, those functor parameters get bound to the actual implementations. After `proc`, the calls show up as going through the bound modules like `PRPc.PseudoRP.fi`. The real issue might be that `inline` in a phoare context treats calls through functor parameters differently than direct module calls, even when the functor is fully instantiated. I might need a different tactic here.

Let me reconsider the naming. The procedure references `PRPc.PseudoRP.fi`, but I should verify what `PseudoRP` is actually called within the `PRPc` clone. Looking at the clone declaration, `PseudoRP` is being cloned as `PRPc` with type and operator substitutions, so there's likely a module also named `PseudoRP` inside that theory that might have a different fully-qualified name in the proof context.

Now I can see the PseudoRP theory (line 690):

```
abstract theory PseudoRP.

module type PseudoRP = {
  proc f(_ : K * D): D
  proc fi(_ : K * D): D
}

module PseudoRP = {
  proc f(k, x) = { return p k x; }
  proc fi(k, x) = { return pi k x; }
}
```

So `PseudoRP.PseudoRP` is the concrete module, and `PseudoRP.fi(k, x) = return pi k x`.
After cloning and importing PseudoRP as PRPc, the module becomes `PRPc.PseudoRP`, where `PRPc.PseudoRP.fi(k, x)` now returns `Pi k x`, which is equivalent to `AESi k x`. In the phoare goal, I see `pi <@ PRPc.PseudoRP.fi(ek, ci)` being called as a concrete procedure, but when I try to inline it with `inline PRPc.PseudoRP.fi.`, the tactic gets rejected.

Let me reconsider whether `inline` is even supported in phoare context. The rejection messages suggest the procedure name was resolved correctly, but the inline tactic itself wasn't accepted—maybe I need to try `inline{1}` with an explicit side specifier, or perhaps `inline` simply isn't available in phoare at all.

Let me explore alternatives like `ecall` to see if that works for handling the procedure call, or fall back to the `seq` approach to break down the five goals systematically.

Actually, stepping back—the core issue is that I need to prove both losslessness and the hoare triple separately. The `hoare.` tactic failed because it couldn't establish losslessness for the called procedures. So I should use `conseq` to decompose this explicitly: prove the hoare part in a hoare context where `inline` works, and handle losslessness separately using tactics like `while true` and `call`. The `0%r = 1%r` contradiction suggests the tactic is trying to prove something impossible, so I need to be more careful about how I structure the proof. Trying different `conseq` syntax forms...

Actually, I'm overcomplicating this. Let me just commit to the `seq` approach and work through the resulting subgoals instead of speculating about the exact syntax. I could also step back and try a completely different strategy — maybe undoing `sp.` and using `conseq` to convert from phoare to hoare plus a separate probability proof, handling each part independently.

But now I'm realizing that `hoare.` did actually produce a hoare goal as the second subgoal. The real problem is the first goal it generated: `0%r = 1%r`, which is obviously false. This suggests the `hoare` decomposition itself is flawed for this particular statement. The issue seems to be that `hoare.` assumes the probability mass allocated to the hoare triple is 0, leaving probability 1 to account for elsewhere — but since 0 ≠ 1, the whole approach breaks down.

Looking at how `hoare.` works in EasyCrypt for a `phoare` statement equal to `1%r`, it tries to decompose using the hoare triple and then verify losslessness through `Pr[f : P => true] = 1%r`. But the underlying formula requires checking that `Pr[f : P => true] >= 1%r`, and if EC can't verify losslessness for procedure calls, it might compute the probability as `0%r` instead.

The core issue is that `hoare.` fails because EC can't infer the losslessness property. Let me try a completely different approach and start fresh.

I could use `bypr` to convert the phoare goal into a probability expression that can be reasoned about logically, though that might not actually simplify things. But I think the most practical path forward is to commit to the `seq` approach and work through the resulting goals, even if there are five of them—many should be straightforward to close.
