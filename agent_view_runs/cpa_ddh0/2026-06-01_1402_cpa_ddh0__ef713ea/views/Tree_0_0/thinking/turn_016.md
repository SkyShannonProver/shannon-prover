# Tree-0.0 · turn 16 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:11:44.519Z -->

**Intent:** `commit_tactic`  
**Payload:** `progress.`

---

`smt(pow_pow).` was rejected. The lemma name might be wrong. Let me try a different approach. 

The key algebraic fact is `(g ^ sk0L) ^ yL = g ^ (sk0L * yL)`. In the DiffieHellman theory, this might be called `gpow_pow` or `group_pow_mult` or similar. Let me try decomposing the goal first with `progress` and then using `smt()` or `algebra`.

Actually, let me think about the exact names. In EasyCrypt's DiffieHellman library:


- `pow_pow`: `(g ^ x) ^ y = g ^ (x * y)` — this is probably the right lemma but the name might be different
- In the DH.G module, it might be `pow_pow` or `gpow_gpow`

Maybe the issue is that `smt` can't handle the `&&` conjunction or the complex structure. Let me try `progress.` first to decompose the goal into simpler subgoals.
