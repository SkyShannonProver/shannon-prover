# Tree-0.0 · turn 27 · commit_tactic

<!-- session 89741c4d-97d4-4e85-92cf-0be265f01f88 · 2026-06-09T21:57:23.829Z -->

**Intent:** `commit_tactic`  
**Payload:** `split; [smt() | move=> _ _ lbad1_R badi_R hinv hproj; smt(nth_out neq_w1_w2)].`

---

Even with the axiom smt balks at the quantified form. Introducing everything manually, then giving smt the out-of-range `nth_out` lemma plus the axiom.
