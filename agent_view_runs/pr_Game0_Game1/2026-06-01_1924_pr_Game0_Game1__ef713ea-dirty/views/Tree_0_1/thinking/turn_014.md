# Tree-0.1 · turn 14 · commit_tactic

<!-- session c9465eb4-3d60-4ffd-9a6f-635b68c15d96 · 2026-06-02T02:48:26.854Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (_: true, (Game1.r \in Log.qs){2}).`

---

Still rejected! Only `call (_: true, bad)` works. There's something fundamentally different about `true` vs any other invariant.

Wait... maybe the issue is that the "upto bad" `call (_: inv, bad)` generates a postcondition check against the overall pRHL postcondition. The postcondition of the pRHL judgment is:

```
(b'{1} = b{1}) = (b'{2} = b{2}) \/ (Game1.r{2} \in Log.qs{2})


```

When `call (_: inv, bad)` generates the postcondition, it produces something like:
```
(={res} /\ inv) \/ bad
```

Which expands to:
```
(b'{1} = b'{2} /\ inv) \/ (Game1.r{2} \in Log.qs{2})
```

For this to imply the overall postcondition, I need `={b` to hold, but that's not guaranteed by the invariant alone.

The key issue is that `b` is a local variable that doesn't get modified after the `a2` call, yet EasyCrypt might not automatically include `={b}` in the postcondition context. With `call (_: true, bad)` instead, the postcondition simplifies to `={res} \/ bad`, and EasyCrypt can verify symbolically that `={b'} /\ ={b}` implies the equality we need.

```
With `call (_: ={Log.qs}, bad)`:
- Postcondition: `(={Log.qs} /\ ={res}) \/ bad` = `={Log.qs, b'} \/ bad`
- For the overall post: same check needed
- But maybe EasyCrypt can't verify this because `={Log.qs}` adds extra constraints?

Hmm, that doesn't make sense. `={Log.qs}` is a WEAKER condition than not having it (since it just adds more info, not less). The implication should still hold.

Unless... EasyCrypt's postcondition check is EXACT, not "implication". Maybe EasyCrypt requires the call postcondition to EXACTLY match the overall postcondition, not just imply it.

With `true`: postcondition is `(={b'} /\ true) \/ bad` = `={b'} \/ bad`. Plus `={b}
```

I'm wondering if EasyCrypt is doing an exact match on postconditions rather than checking logical implication—that would explain why adding `={Log.qs}` causes issues even though it should be weaker, and why the simpler `true` condition works better. from context gives `(b'{1} = b{1}) = (b'{2} = b{2}) \/ bad`.

With `={Log.qs}`: postcondition is `(={b', Log.qs}) \/ bad`. Plus `={b}` from context gives `(b'{1} = b{1}) = (b'{2} = b{2}) /\ ={Log.qs} \/ bad`.

Both should imply the overall postcondition. If EasyCrypt checks exact match, neither would work. If it checks implication, both should work.

Hmm, but `true` works and `={Log.qs}` doesn't. So maybe EasyCrypt DOES check something different.

Wait, I think the real issue might not be the postcondition itself. Let me reconsider what happens when `call (_: inv, bad)` processes the abstract adversary's final call. The `call` tactic generates oracle preservation goals, adversary losslessness goals, and a precondition for remaining code. For the oracle preservation with "upto bad" semantics, EasyCrypt should be checking that the oracle maintains the invariant and bad flag across both sides of the equivalence.

The problem might be that when the invariant is non-trivial, EasyCrypt generates losslessness goals for the oracle that reference the invariant, and these goals fail to discharge because the oracle's losslessness depends on properties that aren't automatically provable. type-check.

Actually, wait. Let me think about this differently. The adversary `A` is declared as `Adv {-LRO, -Log}`, meaning it doesn't have access to `LRO` or `Log` directly. The oracle `Log(LRO)` wraps these modules.

For the "upto bad" call, the oracle `Log(LRO).o` needs to be lossless. `Log(LRO).o` calls `LRO.o`, which is lossless (because `dptxt_ll`). And `Log.o` itself is lossless (it just prepends to a list and forwards). So `Log(LRO).o` is lossless.

But for `phoare[Log(LRO).o{1} : bad ==> bad] = 1%r`, the bad event needs to be monotone in `Log(LRO).o`. Since `Log(LRO).o` prepends to `Log.qs`, the condition `Game1.r \in Log.qs` is monotone. The losslessness ensures termination, so the phoare should hold.

Though maybe EasyCrypt requires establishing losslessness together with the invariant—like `phoare[Log(LRO).o : inv /\ bad ==> bad] = 1%r`. But that's just strengthening the precondition, so it shouldn't matter.

I'm really stuck on why non-trivial invariants fail. Let me try a completely different approach.

Instead of using `byequiv`, let me go back to the original probability goal and split it directly. I'll rewrite the RHS using probability decomposition to separate the cases where `Game1.r \in Log.qs` and where it isn't, then use `byequiv` to relate the two games on the relevant case. I'm going back to the `byequiv` approach and reconsidering whether I can make it work without the "upto bad" call. If I accept the `call (_: true, bad)` that gets generated, the oracle preservation becomes trivial since `true` is always maintained, and the precondition is automatically satisfied. The key insight is that the postcondition `={b'} \/ bad` actually gives us exactly what we need for this proof.

Now I'm working through the precondition from that call: it should be `={c, glob A} /\ !bad`, which translates to `!(Game1.r \in Log.qs){2}`. The question is whether I can establish from the code before the call that `Game1.r` hasn't been added to the log yet.

Actually, I realize the precondition for an "upto bad" call should include both the invariant and the negation of bad, or alternatively just accept that bad has already occurred. So the precondition becomes `(={c, glob A} /\ !bad) \/ bad`, which simplifies nicely since the disjunction with bad makes the whole thing satisfiable — I can establish the equality when bad hasn't happened, and when it has, I'm already in the bad case.

Now I'm checking whether the oracle preservation goal works out with `inv = true`. The goal becomes checking that if the arguments are equal and bad hasn't fired, then either the results are equal or bad fires. This should be provable since the oracle returns consistent results.

But actually, I'm running into a problem: when `inv = true`, I have no information about the internal state of `LRO.m`, so I can't guarantee the results are equal even when the inputs match and bad hasn't occurred yet.

This is strange because EasyCrypt accepted `call (_: true, bad)` and generated goals from it, but those goals turn out to be unprovable since the invariant doesn't actually maintain the oracle coupling. Meanwhile, when I try to use a proper invariant, it gets rejected entirely. The fact that `true` is syntactically accepted but `true` is rejected suggests the real issue isn't about matching postconditions but something deeper about how the invariant itself is being validated.

Let me reconsider what could be wrong with the invariant. The invariant references `LRO.m`, which is a module variable that should be accessible since `Log(LRO).o` accesses it through the oracle. But I'm wondering if there's a scoping issue — maybe after cloning ROM as H and importing H.Lazy, the `Log` module has a different fully qualified name, or there's a name collision since there appear to be two different `Log` modules in play here. clone (`H.Log` which tracks queries) and one defined in the file. Let me check...

Actually, looking at the ROM theory: ROM typically defines `Log` as a logging oracle wrapper. And the file defines its OWN `Log` module. When we `clone import ROM as H`, the ROM's `Log` becomes `H.Log` (or just `Log` if imported).

Wait, looking at the file more carefully: the `clone import ROM as H` statement brings in the lazy oracle via `import H.Lazy`. But does ROM actually define a `Log` module?

Let me check the cross-file module info... Yes! ROM has a `Log` module defined in the EasyCrypt source. So there are two `Log` modules in scope: `H.Log` from the ROM clone and the locally defined one, where the local definition shadows the imported version. The cross-file lemmas like `Log_o_stable` and `Log_init_ll` are likely from ROM's `Log` module.

When I reference `Log.qs` in my invariant, it's using the local `Log.qs`, which is what I want. So shadowing isn't the issue here.

Let me reconsider what's actually failing. Maybe the `call (_: inv, bad)` tactic for "upto bad" has stricter requirements about what `inv` can mention—perhaps it can't reference module variables from the called modules, or it needs to be a proper relational invariant that the tactic can verify. I'm wondering if adding `true /\` before the invariant would help, but that's logically equivalent to the original, so it wouldn't change anything.

Let me try a different approach: remove the outer parentheses and side annotations from the bad event to see if that's causing a parsing issue. If that doesn't work, I'll try accepting `call (_: true, bad)` to prove the losslessness goal first, then examine what the remaining goals look like and strengthen them manually.
