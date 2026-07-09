# Tree-0.0 · turn 6 · commit_tactic

<!-- session 07455470-e8fa-4295-a197-2758a7098fad · 2026-06-06T22:55:33.276Z -->

**Intent:** `commit_tactic`  
**Payload:** `have hc : (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr} / (DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2) = m{hr} by rewrite log_bij !(logg1, logrzM, logDr, logrV); ring.`

---

The division wasn't simplified — `/` is `* inv`, so `logDr` splits it leaving `loge (inv Z)`, which needs `logrV`. Let me add it.
