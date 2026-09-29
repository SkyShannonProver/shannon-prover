# Tree-0.0 · turn 9 · commit_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:42:38.359Z -->

**Intent:** `commit_tactic`  
**Payload:** `pose V := H k (DH.G.g ^ u, DH.G.g ^ w ^ u, (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u * m{hr}); have hc: (DH.G.g ^ x1 * DH.G.g ^ w ^ x2) ^ u * (DH.G.g ^ y1 * DH.G.g ^ w ^ y2) ^ (u * V) = DH.G.g ^ u ^ (x1 + V * y1) * DH.G.g ^ w ^ u ^ (x2 + V * y2); first by rewrite log_bij !(logg1, logrzM, logDr); ring.`

---

`hc` is discharged by the `log_bij; ring` recipe — exactly as in `CCA_DDH0`. Let me commit this, then handle the if-reduction and division.
