# Tree-0.0 · turn 19 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:13:02.691Z -->

**Intent:** `commit_tactic`  
**Payload:** `exact pow_pow.`

---

Now the goal is cleanly: `g ^ sk0L ^ yL = g ^ (sk0L * yL)`

This is the fundamental group exponentiation law. I need to find the right lemma name. Let me try a few:

1. `rewrite pow_pow.`
2. `by algebra.`
3. `by ring.`
4. `smt(pow_pow).`

Actually, let me look at the EasyCrypt DiffieHellman theory. The DH.ec file (DiffieHellman.ec in EasyCrypt) clones from CyclicGroup. 

I found it in CyclicGroup.ec — the GP module defines a lemma that states `(g ^ x) ^ y = g ^ (x * y)`. Since we imported `DH.GP`, this lemma should be accessible. My earlier `smt(pow_pow)` attempt failed, so let me try applying it directly with `exact pow_pow.` or `rewrite pow_pow.`, or if needed, reference it through the module path as `DH.GP.pow_pow`.
