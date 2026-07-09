# Tree-0.0 · turn 1 · commit_tactic

<!-- session 1a1ab548-14a6-4388-a657-8ce8dd3d4233 · 2026-06-11T04:16:53.252Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv=> //.`

---

I'm starting on lemma `PTXT_security`. Let me read the current workspace view first.

The goal is a probability inequality: `Pr[INT_PTXT(MacThenEncrypt(E,M),A).main() : res] <= Pr[WUF_CMA(M, CMAa(E,A)).main() : res]`. Let me read the source file to understand the games involved.
