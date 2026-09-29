# Tree-0.0 · turn 11 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:37:14.805Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (ler_trans (mu dt (mem (map loge (map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog{hr}))))).`

---

`split` succeeded; now I'm on the `mu` bound (the trivial conjunct is pending). I'll bound via `mu_le` to `mem (map loge L1)`, then `mu_mem_le_mu1_size`. First, introduce the transitivity intermediate.
