# Tree-0.0 · turn 20 · commit_tactic

<!-- session 12a54980-bb62-4d41-bd46-c008f2840df5 · 2026-06-01T21:14:00.272Z -->

**Intent:** `commit_tactic`  
**Payload:** `by rewrite expM.`

---

`exact pow_pow.` was rejected. The lemma name `pow_pow` might not exist in this context. Let me look at the actual DiffieHellman.ec theory file to find the correct lemma name. Let me search for it in the EasyCrypt source files.

Actually, let me look at the actual source file to find what lemmas are available.

The DiffieHellman theory clones from `CyclicGroup` as `G`, and then from `G.PowZMod` as `GP`. So the group lemmas are in `G` and `GP`, which come from the `Group.ec` and `CyclicGroup.ec` files.

Let me look at the Group.ec file to find the power-of-power lemma.

Found it! Line 488:
```
lemma expM (x : group) (a b : exp) : x ^ (a * b) = x ^ a ^ b.
```

This is `expM` in the `PowZMod` theory. And it says `x ^ (a * b) = x ^ a ^ b`, which means `(x ^ a) ^ b = x ^ (a * b)` (reversed direction from what I want).

Wait, actually the lemma states `x ^ (a * b) = x ^ a ^ b`. The `^` is right-associative? No, `x ^ a ^ b` is `(x ^ a) ^ b`. 

So the lemma gives me `g ^ (sk0L * yL) = (g ^ sk0L) ^ yL`, but my goal is the reverse: `(g ^ sk0L) ^ yL = g ^ (sk0L * yL)`. I can apply `expM` backwards with `rewrite -expM` to flip the equality. I'm realizing that `rewrite expM` should work because it matches the pattern `x ^ (a * b)` on the RHS and rewrites it to `x ^ a ^ b`, making both sides identical. But I need to check if this lemma is in the `PowZMod` context where I'm working.

Looking at the file structure, `expM` is defined in `PowZMod` around line 488, and in elgamal.ec I'm importing from the cloned DiffieHellman module which should give me access to the necessary theories and lemmas.

Since `GP` contains `expM` and I've imported `DH.GP`, I should be able to reference it directly or through the module path. There might be naming conflicts with the overloaded `exp` operator, but `expM` from `PowZMod` should be the right lemma for the power operation. Let me try applying it with `rewrite expM.` or through the full module path if needed.

Actually, I need to check the direction carefully. The lemma `expM` states that `x ^ (a * b) = x ^ a ^ b`, which means rewriting the right-hand side `g ^ (sk0L * yL)` left-to-right gives me `g ^ sk0L ^ yL`. That matches the left-hand side exactly, so this should close the goal by reflexivity. `by rewrite expM.` should work.
