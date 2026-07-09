# Tree-0.1 · turn 1 · probe_tactic

<!-- session 023937ce-0bad-4bd1-84e6-c790185a3766 · 2026-06-01T06:55:38.956Z -->

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

This is asking: if `s1` and `s2` are both restricted to `[0, n)`, then `{n} ∪ s1 = {n} ∪ s2` iff `s1 = s2`.


The forward direction is immediate by substitution. For the backward direction, since `n` doesn't appear in either `s1` or `s2` by the restriction property, I can remove it from both sides of the union equation to conclude they're equal. I should try moving the hypotheses into the context and rewriting with the restriction definition, then applying the relevant lemmas about set membership. The forward direction follows immediately by substitution, but the backward direction requires showing that if the fsets are equal, then the underlying sets must be equal. Since `n` is excluded from both sets by the restriction property, I can use set extensionality to argue that for any element `x`, membership in `s1` is equivalent to membership in `s2`, which gives me the equality I need.

Now let me analyze the goal:

```
n: int
s1: int fset
s2: int fset
------------------------------------------------------------------------
is_restr s1 n =>
is_restr s2 n => (fset1 n `|` s1 = fset1 n `|` s2) = (s1 = s2)
```

This is a pure ambient logic goal. The navigation suggests a fast-track probe: `move=> *; rewrite /is_restr; smt(restrS is_restrS is_restr_addS).`


Let me try the fast-track approach first, and if that doesn't work, I'll explore alternatives using `nin_is_restr` and `fsetP`.
