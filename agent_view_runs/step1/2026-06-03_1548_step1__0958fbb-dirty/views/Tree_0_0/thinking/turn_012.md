# Tree-0.0 · turn 12 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T22:58:07.292Z -->

**Intent:** `probe_tactic`  
**Payload:** `rewrite -(pr_CCP_OCCP I_stateless G1 &m).`

---

Back at the Pr equality. Now rewrite the LHS from `OChaChaPoly` to `GenChaChaPoly` using `pr_CCP_OCCP` instantiated with `I_stateless` and the wrapper `G1`. Probing right-to-left rewrite directly on the goal.
