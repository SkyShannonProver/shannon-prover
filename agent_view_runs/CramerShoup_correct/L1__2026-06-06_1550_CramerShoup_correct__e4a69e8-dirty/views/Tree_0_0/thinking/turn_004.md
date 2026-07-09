# Tree-0.0 · turn 4 · commit_tactic

<!-- session 07455470-e8fa-4295-a197-2758a7098fad · 2026-06-06T22:54:53.957Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hd : (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u * (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * v) = DH.G.g ^ u ^ (x1 + v * y1) * DH.G.g ^ w ^ u ^ (x2 + v * y2) by rewrite log_bij !(logg1, logrzM, logDr); ring.`

---

Pose succeeded. Now prove the decryption-condition equality.
