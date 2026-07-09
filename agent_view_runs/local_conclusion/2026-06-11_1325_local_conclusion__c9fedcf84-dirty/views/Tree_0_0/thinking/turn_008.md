# Tree-0.0 · turn 8 · commit_tactic

<!-- session abd26ef5-2223-44fa-90ae-640e8ee18bd8 · 2026-06-11T20:37:48.171Z -->

**Intent:** `commit_tactic`  
**Payload:** `inline{1} CBCa.SKEa.RCPA.RCPA_Wrap(Random).enc; inline{2} CBCa.SKEa.RCPA.RCPA_Wrap(CBCa.SKEa.RCPA.Ideal).enc.`

---

Now the innermost wrapper. Inlining `RCPA_Wrap(...).enc` to expose the bare `Random.enc` / `Ideal.enc` calls.
