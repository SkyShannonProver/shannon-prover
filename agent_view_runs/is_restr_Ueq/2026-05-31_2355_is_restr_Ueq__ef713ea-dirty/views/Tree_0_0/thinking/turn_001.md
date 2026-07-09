# Tree-0.0 · turn 1 · probe_tactic

<!-- session 2e75d736-140d-4a8e-9742-884a1444224e · 2026-06-01T06:55:29.867Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> *; rewrite /is_restr; smt(restrS is_restrS is_restr_addS).`

---

Let me analyze the current proof goal for `is_restr_Ueq`:

```
n: int
s1: int fset
s2: int fset
------------------------------------------------------------------------
is_restr s1 n =>
is_restr s2 n => (fset1 n `|` s1 = fset1 n `|` s2) = (s1 = s2)
```

This is a pure logic goal about finite sets. We need to prove that if `s1` and `s2` are both restricted to `[0, n)`, then `{n} ∪ s1 = {n} ∪ s2` iff `s1 = s2`.


The key insight is that `is_restr s1 n` means all elements of `s1` are in `[0, n)`, so `n` doesn't appear in either set. This means adding `{n}` to both sets preserves the equality relationship—if the unions are equal, then `s1` and `s2` must be equal since they can't contain `n` themselves. The backward direction is trivial: if `s1 = s2`, then `{n} ∪ s1 = {n} ∪ s2`.

Now I'm looking at the available lemmas about `is_restr` and thinking through a proof strategy. The goal is to show an equality between a boolean expression involving `fset1 n` and set operations, so I should unfold the definition of `is_restr` and try using the relevant lemmas with an SMT solver to handle the set-theoretic reasoning.

Let me probe the fast-track suggestion first to see if it closes the goal directly.
