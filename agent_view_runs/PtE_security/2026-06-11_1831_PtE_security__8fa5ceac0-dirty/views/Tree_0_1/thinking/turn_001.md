# Tree-0.1 · turn 1 · commit_tactic

<!-- session 896fb88e-48e7-4f44-b08a-30ed5979749c · 2026-06-12T01:35:35.103Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite -(PtE.RCPA_preservation (<: IV_Wrap(CBC(PseudoRP))) (<: RCPA_WUF_RCPA.RCPAa(MAC, RCPA_QueryBounder(A))) &m).`

---

I'm picking up the prover session for `PtE_security`. Let me read the current workspace view first.

The RHS of the goal matches `RCPA_preservation` from the `RCPA_pad` clone (`PtE`). Let me read the top of `RCPA_pad.eca` to understand the clone structure.
