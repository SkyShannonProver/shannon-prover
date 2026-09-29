# Tree-0.1 · turn 17 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:11:39.585Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite pow_pow.`

---

`progress` reduced everything to exactly the algebraic identity I expected:

```
(g ^ sk0L ^ yL * if bL then result_R.`2 else result_R.`1) =
g ^ (sk0L * yL) * if bL then result_R.`2 else result_R.`1
```

This needs `g ^ sk0L ^ yL = g ^ (sk0L * yL)`, which is the standard group law `(g^a)^b = g^(a*b)`.

In EasyCrypt's DiffieHellman theory, this should be the lemma `pow_pow` or similar. 

Now I need to find the right lemma in the CyclicGroup theory that DiffieHellman builds on—it's likely `gpow_pow` or `expM`, which states that repeated exponentiation can be collapsed into a single exponentiation with multiplied exponents. I should try using `algebra.` or `ring.` tactics to apply this automatically.

Actually, looking at the full goal more carefully, I can use `congr.` to split the equality into the exponentiation part and the conditional part, then focus on proving `g ^ sk0L ^ yL = g ^ (sk0L * yL)` separately before handling the multiplication with X.

For that core exponentiation equality, I'll try a few tactics: `smt()` might handle the group algebra directly, or I could use `algebra.` for algebraic simplification, `ring.` for ring reasoning, or manually apply the power-of-power lemma with `congr; first by rewrite pow_pow.` Let me start with `algebra.` since that's typically the go-to for this kind of simplification.

Actually, I'm realizing `algebra` isn't a standard EasyCrypt tactic—I should reach for `ring`, `field`, or `smt()` instead. The relevant lemmas are probably in the cyclic group theory, where `g ^ a ^ b = g ^ (a * b)` should be available. Let me just try `smt()` and let the SMT solver handle the group axioms, or fall back to `congr.` if that doesn't work.

The real issue is that `smt()` might not automatically pull in the group power lemmas unless they're explicitly in scope. I should look for the specific lemma in EasyCrypt's CyclicGroup module—it's likely stated as a rewrite rule for exponentiation composition. Once I find it, I can use `rewrite` to apply it directly, then finish with `trivial.` I'm realizing that `rewrite pow_pow` should match `g ^ sk0L ^ yL` and transform it to `g ^ (sk0L * yL)`, which would make both sides of the equation identical and let me close the goal. I'm realizing the pattern here—`g ^ sk0L ^ yL` parses as `(g ^ sk0L) ^ yL`, and the `pow_pow` lemma should rewrite this to `g ^ (sk0L * yL)` where the multiplication is in the exponent ring. Since we've already imported the necessary group theory definitions, I should be able to apply this rewrite directly.
