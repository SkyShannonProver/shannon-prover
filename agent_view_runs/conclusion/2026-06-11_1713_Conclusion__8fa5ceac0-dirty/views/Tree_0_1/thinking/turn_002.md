# Tree-0.1 · turn 2 · commit_tactic

<!-- session e71bc6a0-2cf3-4e7f-ae02-bf353a3bbd0d · 2026-06-12T00:15:02.537Z -->

**Intent:** `commit_tactic`  
**Payload:** `have QBA_ll: forall (O <: RCPA_Oracles{-QueryBounder(A)}), islossless O.enc => islossless QueryBounder(A, O).distinguish.`

---

Intro accepted. Now I'll establish losslessness of `QueryBounder(A)` so I can apply the `reduction` lemma.
