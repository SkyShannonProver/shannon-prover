# Tree-0.1 · turn 2 · probe_tactic

<!-- session 023937ce-0bad-4bd1-84e6-c790185a3766 · 2026-06-01T06:56:09.922Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> h1 h2; smt(nin_is_restr fsetP in_fsetU in_fset1).`

---

The fast-track failed because `is_restrS` is not found as a lemma name in the EasyCrypt session. The file defines `is_restrS` but it might not be proven (it might have `admit` in it or might not be loaded). Let me check - looking at the source file, `is_restrS` is defined before `is_restr_Ueq` and its proof is:

```
lemma is_restrS n s :
  0 <= n =>
  is_restr s n => is_restr s (n + 1).


```

Completing the proof...

The lemma should be available since it's defined before `is_restr_Ueq`, so the error about not finding it might be a name resolution issue. Let me try a more direct approach to work around this.

The goal is to prove that for two restricted sets, their unions with a singleton are equal if and only if the sets themselves are equal. I'll introduce the hypotheses and split this into two directions: one direction follows by congruence, and the other uses extensionality along with the restriction properties to reason about membership. I'm working through different tactic approaches to prove this equality of finite sets. The key insight is that equality on booleans in EasyCrypt is really an iff, so I need to show both directions. I'm trying various combinations like using `eq_iff` to split into forward and backward implications, or potentially leveraging the `nin_is_restr` lemma with SMT automation to handle the set membership reasoning directly. Trying a simpler approach with SMT to see if it can handle the finite set reasoning directly with those lemmas.
