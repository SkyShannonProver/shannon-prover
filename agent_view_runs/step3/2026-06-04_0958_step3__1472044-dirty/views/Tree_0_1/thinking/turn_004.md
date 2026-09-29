# Tree-0.1 · turn 4 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:01:34.464Z -->

**Intent:** `commit_tactic`  
**Payload:** `proc.`

---

The error detail isn't in the goal panel. Let me read the manager result file to see why `inline *` was rejected.

No error text is surfaced under this profile. The likely cause: after `byequiv` the goal is at the *procedure* level (it shows `…distinguish ~ …main`), so `inline` over the bodies isn't available until I enter the procedures. Let me reduce to the body-statement judgment with `proc`.
