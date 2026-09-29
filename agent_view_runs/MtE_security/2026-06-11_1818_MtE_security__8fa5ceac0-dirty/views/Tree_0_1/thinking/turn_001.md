# Tree-0.1 · turn 1 · commit_tactic

<!-- session 678f18e4-53cf-49b7-9b5d-d7daac7a142a · 2026-06-12T01:20:47.176Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap(CBC(PseudoRP)))) (<: MAC) (<: RCPA_QueryBounder(A)) &m).`

---

I'll start by reading the latest workspace view to see the current proof state.

The goal is an equality of two absolute probability differences (MtE reduction). Let me look at the source file for the lemma statement and sibling lemmas.

Let me check the MAC module definition to know how to discharge its losslessness premises.
