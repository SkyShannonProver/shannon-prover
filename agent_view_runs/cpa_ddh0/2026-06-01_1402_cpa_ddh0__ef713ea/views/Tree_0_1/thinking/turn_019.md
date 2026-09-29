# Tree-0.1 · turn 19 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:12:24.035Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt().`

---

Now the goal is exactly:
```
g ^ sk0L ^ yL = g ^ (sk0L * yL)
```

This is the pure group exponentiation law. Let me try different lemma names:

1. `smt().` — let the SMT solver handle it
2. `rewrite expM.` — another possible name
3. `rewrite GP.pow_pow.` — qualified name
4. `algebra.` — algebraic simplification

Actually, in EasyCrypt's CyclicGroup.ec, I recall the relevant lemma is often called `pow_pow` or `expgM`. 

Since we imported `DH.GP`, I should try different names for the exponentiation law. Let me start with `smt()` as the most general approach. But wait—the error said the tactic was rejected entirely, which means the lemma name itself is wrong. I need to figure out what's actually available in the CyclicGroup theory that DiffieHellman imports.

Looking at EasyCrypt's source, `CyclicGroup.ec` defines the exponentiation law within `PowZMod`, and since we're cloning DiffieHellman which clones CyclicGroup, the lemma should be accessible through `DH.GP`. But the rejection suggests it's not being found, so either the lemma doesn't exist in this version of EasyCrypt or it has a different name. Let me try `smt()` first, or look for an `algebra` tactic if that's available.

Actually, I'm realizing the issue might be simpler—looking at the DiffieHellman clone more carefully, `DH.GP` is imported, so `pow_pow` from the CyclicGroup PowZMod theory should be in scope. But maybe it's named differently in this version. Let me try applying the lemma directly with `exact pow_pow` or `apply pow_pow`, or pass it to the SMT solver with `smt(pow_pow)`.
