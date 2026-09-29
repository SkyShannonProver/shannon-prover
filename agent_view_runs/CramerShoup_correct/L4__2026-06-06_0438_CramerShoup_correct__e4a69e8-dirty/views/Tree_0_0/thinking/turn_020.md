# Tree-0.0 · turn 20 · commit_tactic

<!-- session 5234f886-6033-4a40-9812-c27131140e4b · 2026-06-06T11:47:50.055Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite hc /=; have hD: (DH.G.g ^ z1 * DH.G.g ^ w ^ z2) ^ u = DH.G.g ^ u ^ z1 * DH.G.g ^ w ^ u ^ z2; first by rewrite log_bij !(logg1, logrzM, logDr); ring. rewrite -hD log_bij !(logg1, logrzM, logDr) -expN !(logg1, logrzM, logDr); ring.`

---

The probe was accepted with no residual preview — the chain closes the goal. Let me commit it.
