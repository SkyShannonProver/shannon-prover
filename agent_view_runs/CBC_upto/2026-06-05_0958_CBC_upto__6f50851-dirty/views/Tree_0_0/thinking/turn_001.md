# Tree-0.0 · turn 1 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:04:24.944Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite (doublequery_eq PRFi &m) (doublequery_eq Sample &m).`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the source file to understand the lemma and surrounding context.

This is the `CBC_upto` upto-bad lemma. Let me study the helper lemmas available in the `Reduce` section:

- `doublequery_eq (F)`: `Pr[CBC_Oracle(F):res] = Pr[CBC_Oracle(DoubleQuery(F)):res]`
- `DQ_Sample_Compute_eq`: equiv `CBC_Oracle(DoubleQuery(Sample)).enc ~ Compute.enc`
- `DQ_Sample_Compute_pr`: `Pr[CBC_Oracle(DoubleQuery(Sample)):DoubleQuery.bad] = Pr[Compute:Compute.bad]`

So the intended proof is: rewrite both games to `DoubleQuery`-wrapped form, rewrite the RHS bad to `DoubleQuery.bad`, then do an upto-bad `byequiv` between `DoubleQuery(PRFi)` and `DoubleQuery(Sample)` (equal until a query collides = `DoubleQuery.bad`).

Let me consult the advisor on this plan before committing tactics, since the upto-bad loop step is the crux.

Advisor confirms the decomposition. Let me commit incrementally for clean feedback. First, the two `doublequery_eq` rewrites.
