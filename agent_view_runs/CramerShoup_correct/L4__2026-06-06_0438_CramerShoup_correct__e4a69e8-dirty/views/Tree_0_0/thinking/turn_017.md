# Tree-0.0 · turn 17 · probe_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:46:05.418Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2; first by rewrite log_bij !(logg1, logrzM, logDr); ring. rewrite -hD; smt(@DH.G).`

---

`logDr` is `DH.G.logDr` (the `loge` family lives in `DH.G`). For the final cancellation `X * m / X = m`, I've already rewritten the denominator to match the numerator via `-hD`. Let me probe closing that with the group theory's own lemmas.
