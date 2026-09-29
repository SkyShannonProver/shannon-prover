# Tree-0.0 · turn 35 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:10:17.354Z -->

**Intent:** `probe_tactic`  
**Payload:** `call poly_mac1. auto. if => //. wp. call chacha_enc1. auto. auto.`

---

Let me check whether `call poly_mac1. auto.` closed part1.

Part1 closes (4→3). Now part2 is the `if (t=t')` branch with matching guards (`t,t'` equal in pre). Probing the full dec remainder: `call poly_mac1. auto. if => //. wp. call chacha_enc1. auto. auto.`
