# Tree-0.1 · turn 13 · commit_tactic

<!-- session 898dc637-b1a0-4311-a875-97cd3c0aa65a · 2026-06-04T17:06:54.330Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{2} CPA_CCA_Orcls(EncRnd).enc.`

---

Now relate the two `enc` calls. I'll inline only the `CPA_CCA_Orcls` wrapper (not the encapsulated `ChaCha`/`Poly`/`cc` procedures, per the pitfall note) to expose the inner SKE call and the `Mem.lc` logging. Start with the right side.
