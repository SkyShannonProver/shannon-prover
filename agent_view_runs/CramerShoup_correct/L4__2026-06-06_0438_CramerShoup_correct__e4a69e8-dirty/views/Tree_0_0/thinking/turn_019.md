# Tree-0.0 · turn 19 · probe_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:47:36.548Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2; first by rewrite log_bij !(logg1, logrzM, logDr); ring. rewrite -hD log_bij !(logg1, logrzM, logDr) -expN !(logg1, logrzM, logDr); ring.`

---

`DH.G.expN: x ^ -k = inv (x ^ k)` — so `-expN` turns `inv (Y^u)` into `Y^(-u)`, eliminating the inverse atom. Combined with `-hD` (making the denominator a single power), the `log_bij; ring` recipe should now close. Let me probe the full chain.
