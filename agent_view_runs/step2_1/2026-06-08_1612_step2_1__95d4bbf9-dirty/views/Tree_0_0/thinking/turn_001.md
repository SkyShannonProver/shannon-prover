# Tree-0.0 · turn 1 · commit_tactic

<!-- session 97e6a0e6-3ebd-4e69-827b-9ef0ceb80f2b · 2026-06-08T23:16:45.033Z -->

**Intent:** `commit_tactic`  
**Payload:** `have <- : Pr[CCA_game(A, RealOrcls(StLSke(St))).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res].`

---

I'll start by reading the current workspace view to understand the proof state.

Let me read the followup and the lemma source to understand context.

Let me read the lemma source file and its context.

This is a hard CCA-to-CPA reduction with a UFCMA failure term. Let me understand the relevant module definitions.

Let me examine the key module definitions around CCA_CPA_Adv, UFCMA, St, StLSke.

This is cloned from a `CCA_CPA_UFCMA` theory which likely has a generic reduction lemma. Let me find it.

Now I understand the architecture: `step2_1` mirrors the generic `CCA_CPA_UFCMA.CCA_CPA_UFCMA` lemma. Let me examine `OChaChaPoly`, `St`, and how the cloned generic lemma is parameterized.

Let me look at the section declarations (the `A`, axioms) that are in scope for step2_1.

Let me confirm a few definitions (`ChaChaPoly.kg`, `GenChaChaPoly`, `dkey`) before committing.

The structure is clear. The plan: prove `Pr[…StLSke(St)…] = Pr[…OChaChaPoly(IFinRO)…]`, rewrite, then apply the generic `CCA_UFCMA.CCA_CPA_UFCMA` lemma. Let me load the MCP tool.

I'll commit the first tactic: introduce the probability equality so the LHS matches the generic lemma.
