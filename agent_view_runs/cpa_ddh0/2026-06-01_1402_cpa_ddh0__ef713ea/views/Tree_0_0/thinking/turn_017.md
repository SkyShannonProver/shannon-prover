# Tree-0.0 · turn 17 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:12:07.176Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt().`

---

`progress.` solved all the trivial subgoals and left just the key algebraic one:

```
(g ^ sk0L ^ yL * if bL then result_R.`2 else result_R.`1) =
g ^ (sk0L * yL) * if bL then result_R.`2 else result_R.`1
```

This is equivalent to showing `g ^ sk0L ^ yL = g ^ (sk0L * yL)`, since the rest (the multiplication by the conditional) is the same on both sides.

The lemma `(g ^ x) ^ y = g ^ (x * y)` is a standard group theory fact. 

Now I need to find where this is defined in EasyCrypt's DiffieHellman library. Given that we imported `DH.DDH DH.G DH.GP DH.FD DH.GP.ZModE`, the power-of-power lemma should be available somewhere in the cyclic group theory, possibly under a name like `pow_pow` or accessed through the group module directly. I'm wondering if `congr` will create multiple subgoals, so let me explore other tactics like `smt` with the power law lemma, `algebra`, or `ring`. In EasyCrypt's cyclic group, the fundamental property is that `(g ^ a) ^ b = g ^ (a * b)`, which should be available as a basic axiom. Let me start by trying `smt()` without hints to see if it can solve this directly.
