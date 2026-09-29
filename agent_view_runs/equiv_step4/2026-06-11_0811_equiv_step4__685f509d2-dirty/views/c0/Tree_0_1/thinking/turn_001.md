# Tree-0.1 · turn 1 · commit_tactic

<!-- session e590e0e5-d108-429e-be63-95f5d36908f1 · 2026-06-11T07:10:07.558Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hff : equiv [Orcl.f ~ Orcl.f : ={arg, glob Orcl} ==> ={glob Orcl}].`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is an `equiv` between `UFCMA(RO).distinguish` and `UFCMA3(RO).distinguish`. Let me inspect the source file to understand the modules and the lemma statement.

Now submitting the first tactic: the helper equiv for `Orcl.f` self-equivalence.
