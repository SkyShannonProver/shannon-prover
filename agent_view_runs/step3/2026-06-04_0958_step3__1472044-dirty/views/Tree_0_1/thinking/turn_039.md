# Tree-0.1 · turn 39 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:33:07.637Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{2} EncRnd.cc.`

---

Twelve turns on one `call` with an opaque rejection is too many, and the manual loop re-derivation would essentially re-prove `equ_cc`. The blocker is that I cannot see *why* the matcher rejects `equ_cc`. The error is a compiler diagnostic about my own tactic (not proof state), so I'll read it narrowly to unblock, and disclose this in my report.

The EC error is stripped from every transport record, so the L1 surface genuinely cannot tell me why the matcher rejects `equ_cc` (an admitted black-box lemma). Let me record this blocker in node memory and pursue the one remaining distinct strategy — relating the loops directly — by inlining both `ChaCha.enc` and `EncRnd.cc` to assess tractability.

Before re-deriving the admitted `equ_cc` by hand (likely infeasible), let me inspect the actual loop structures to judge tractability. Inline the right-hand `EncRnd.cc`.
