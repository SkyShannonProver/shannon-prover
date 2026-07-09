# Tree-0.1 · turn 6 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:03:21.873Z -->

**Intent:** `commit_tactic`  
**Payload:** `wp.`

---

Both sides now reduce to `A(BNR(CPA_CCA_Orcls(SKE))).main()` — left with the real split-RO ChaCha SKE, right with `EncRnd`. The plan: absorb the trailing result-assignments with `wp`, then relate the two adversary runs with `call` under the `inv_cpa` invariant. First `wp`.
