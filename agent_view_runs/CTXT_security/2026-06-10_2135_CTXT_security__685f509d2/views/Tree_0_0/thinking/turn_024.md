# Tree-0.0 · turn 24 · commit_tactic

<!-- session f8563eb0-33e2-483a-a365-92671a67224b · 2026-06-11T04:47:39.112Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> &2 _; proc; wp; call (EtM_dec_ll E M E_dec_ll M_verify_ll); auto.`

---

Verify equiv closed. Now side-1 verify losslessness — route it through the file's `EtM_dec_ll` helper lemma.
