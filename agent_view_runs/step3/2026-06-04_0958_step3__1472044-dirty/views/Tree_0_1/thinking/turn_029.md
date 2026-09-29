# Tree-0.1 · turn 29 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:15:14.259Z -->

**Intent:** `commit_tactic`  
**Payload:** `call (equ_cc (n{1}) (SplitC2.I1.RO.m{1}) (SplitC2.I2.RO.m{1})).`

---

`call (equ_cc …)` was rejected. Let me read the underlying error.

No error text under this profile. A likely cause is argument parsing: `equ_cc n{1} …` may bind `{1}` to the whole application rather than to `n`. Let me parenthesize each memory-indexed argument.
