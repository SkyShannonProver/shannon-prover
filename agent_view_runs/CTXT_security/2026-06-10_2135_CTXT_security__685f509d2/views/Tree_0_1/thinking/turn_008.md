# Tree-0.1 · turn 8 · commit_tactic

<!-- session 32db57e0-fb2e-4cac-a35b-be9ba42eaabf · 2026-06-11T04:48:38.169Z -->

**Intent:** `commit_tactic`  
**Payload:** `by inline *; wp; call M_verify_ll; auto.`

---

Hoare half closed. Now the lossless half of `Sim.verify` — inline the wrapper and discharge with `M_verify_ll`.
