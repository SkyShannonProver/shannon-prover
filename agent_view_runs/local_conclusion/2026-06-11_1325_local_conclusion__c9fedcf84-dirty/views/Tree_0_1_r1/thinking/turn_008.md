# Tree-0.1.r1 · turn 8 · commit_tactic

<!-- session ee589c25-2d68-4d07-a5d2-61c45dae1522 · 2026-06-11T20:51:03.392Z -->

**Intent:** `commit_tactic`  
**Payload:** `by proc; inline *; wp; call O_enc_ll; auto.`

---

Two subgoals now: `Sim.enc` losslessness first. Its body is concrete wrappers around `O.enc`.
