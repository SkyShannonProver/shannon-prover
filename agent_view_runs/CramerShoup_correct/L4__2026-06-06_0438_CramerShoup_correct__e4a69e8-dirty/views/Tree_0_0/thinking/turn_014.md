# Tree-0.0 · turn 14 · probe_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:44:35.118Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2; first by rewrite log_bij !(logg1, logrzM, logDr); ring. rewrite -hD.`

---

The hints point to `expN` for inverses. Let me take the cleanest route: prove the denominator equals the `c0`-power (pure group equality, no inverse — like `CCA_DDH0` line 302), rewrite it, and inspect the residual cancellation goal.
