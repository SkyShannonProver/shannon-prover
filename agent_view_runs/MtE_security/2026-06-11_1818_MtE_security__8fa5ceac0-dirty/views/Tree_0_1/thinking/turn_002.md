# Tree-0.1 · turn 2 · commit_tactic

<!-- session 678f18e4-53cf-49b7-9b5d-d7daac7a142a · 2026-06-12T01:23:43.285Z -->

**Intent:** `commit_tactic`  
**Payload:** `have RP := RCPA_WUF_RCPA.RCPA_preservation (<: PadThenEncrypt(IV_Wrap(CBC(PseudoRP)))) (<: MAC) (<: RCPA_QueryBounder(A)) &m.`

---

The apply was rejected with a proof-term mismatch. Let me see the full error to find the discrepancy.

The error is a proof-term conclusion mismatch. Let me inspect the MtE theory header to check the exact types/module signatures involved.
