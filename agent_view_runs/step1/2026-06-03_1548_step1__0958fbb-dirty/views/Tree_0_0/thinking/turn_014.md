# Tree-0.0 · turn 14 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:59:03.145Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).`

---

Diagnose shows no EC error captured — the failure was the unqualified `pr_CCP_OCCP` resolving ambiguously (it exists in both `OpCCinit` and `OpCCRO`, which have different `globS`/`Init` types — hence "incompatible module type"). Let me qualify it as `OpCCinit.pr_CCP_OCCP`.
