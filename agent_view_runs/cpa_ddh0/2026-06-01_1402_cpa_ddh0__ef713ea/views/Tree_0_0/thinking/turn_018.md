# Tree-0.0 · turn 18 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:12:50.497Z -->

**Intent:** `commit_tactic`  
**Payload:** `congr.`

---

`smt()` failed too. The SMT solver can't handle group theory. I need to provide the right lemma hint or use a different tactic.

The goal is:
```
(g ^ sk0L ^ yL * if bL then result_R.`2 else result_R.`1) =
g ^ (sk0L * yL) * if bL then result_R.`2 else result_R.`1
```

I need to show `g ^ sk0L ^ yL = g ^ (sk0L * yL)`. The conditional part is the same on both sides.


Let me try `congr.` to isolate the two parts, then search for the exponentiation associativity lemma in the DiffieHellman theory where the group operations are defined through `CyclicGroup`.

I'm trying different approaches to handle the power law `(g ^ a) ^ b = g ^ (a * b)` — `pow_pow` seems like the natural name, but it didn't work with `smt`, so maybe it's in a different namespace or I need to use `algebra` for group equations instead. I'm trying to figure out the right lemma name for the power-of-power rule in EasyCrypt's group theory. The law should be that `(g ^ a) ^ b = g ^ (a * b)`, but I need to check whether `^` is only defined for the generator or works on arbitrary group elements. Looking at how `DH.G` and `DH.GP` are structured, I should try tactics like `smt(DH.G.pow_pow)` or similar to see what lemmas are actually available in the CyclicGroup module. group properties" or "group pow". The lemma might be `DH.GP.pow_pow` but since we imported `DH.GP`, it should just be `pow_pow`.

But `smt(pow_pow)` failed. Maybe the lemma name is different. Let me check by looking at the EasyCrypt source.

Actually, let me try different approaches: rewriting with `pow_pow` directly, using `congr` and `ring` to separate the goal, combining `congr` with `smt`, or using `by rewrite pow_pow` to close it. Let me start with `congr` to see if that helps break down the goal.
