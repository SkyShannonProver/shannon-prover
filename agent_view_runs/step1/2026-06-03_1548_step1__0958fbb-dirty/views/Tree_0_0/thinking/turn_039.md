# Tree-0.0 · turn 39 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:11:24.576Z -->

**Intent:** `probe_tactic`  
**Payload:** `congr.`

---

First congr subgoal closed — `step1`'s first half is done. Now the second half: `- Pr[OChaChaPoly(IFinRO)...] = - Pr[Distinguish(D(A),IndRO)...]`. This mirrors the first half but uses the **OpCCRO** clone (IFinRO returns an fmap), with invariant `OCC.gs{1}=RO.m{2}` and lemmas `poly_mac2`/`chacha_enc2`. Let me strip the negation with `congr.` first.
