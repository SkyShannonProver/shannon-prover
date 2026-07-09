# Tree-0.1 · turn 9 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:04:32.538Z -->

**Intent:** `commit_tactic`  
**Payload:** `sp.`

---

Both sides are the same `BNR.enc` wrapper. The guard `check_plaintext BNR.lenc p` matches across sides (`lenc` equal by the invariant, `p` equal by arg). Let me consume the `c <- witness` assignment with `sp`, then split the conditional.
