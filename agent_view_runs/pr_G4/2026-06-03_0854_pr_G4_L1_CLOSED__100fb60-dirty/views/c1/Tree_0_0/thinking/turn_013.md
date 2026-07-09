# Tree-0.0 · turn 13 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:38:09.788Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (ler_trans (PKE_.qD%r * (1%r / order%r))); last by smt().`

---

Goal 1 done. Now goal 2: `mu dt (mem (map loge L1)) <= qD/order`. Bound via `qD * (1/order)` and `mu_mem_le_mu1_size`.
