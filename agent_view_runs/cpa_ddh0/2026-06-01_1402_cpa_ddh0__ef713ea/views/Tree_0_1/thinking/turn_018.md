# Tree-0.1 · turn 18 · commit_tactic

<!-- session 8696af5a-7961-48ff-9bd3-5f32c202509d · 2026-06-01T21:12:02.003Z -->

**Intent:** `commit_tactic`  
**Payload:** `congr.`

---

The tactic was rejected. `pow_pow` might not be the right lemma name, or it might not be directly in scope. Let me try different approaches:

1. `smt(pow_pow).` — maybe smt can close it with the hint
2. `algebra.` — algebraic simplification
3. `ring.` — ring reasoning
4. `smt().` — let smt try on its own
5. `congr.` — split the goal first

Let me also think about what the actual lemma name might be. In the DiffieHellman.ec theory:
- The group is from `CyclicGroup`


- `pow_pow` might be in `CyclicGroup.PowZMod`
- We imported `DH.GP` which is the power module

The issue might be that `pow_pow` isn't the actual name. Let me try qualifying it as `GP.pow_pow` or using `smt(GP.pow_pow)` instead, since looking at the imports, `DH.GP` is the cyclic group's power module.

In EasyCrypt's standard library, the exponentiation lemma for `(g^a)^b = g^(a*b)` is likely named something like `gpow_gpow` or `pow_mul`. The SMT solver might handle this directly, or I could try `congr` to break it down into simpler pieces.
