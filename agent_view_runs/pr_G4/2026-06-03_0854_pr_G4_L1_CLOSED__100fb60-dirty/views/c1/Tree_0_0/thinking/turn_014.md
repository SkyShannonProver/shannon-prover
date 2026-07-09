# Tree-0.0 · turn 14 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:38:22.707Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (mu_mem_le_mu1_size dt (map loge (map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog{hr})) (1%r / order%r) PKE_.qD); [ by rewrite !size_map; smt() | by move=> x; rewrite dt1E ].`

---

Now apply `mu_mem_le_mu1_size` and discharge its two side conditions (size bound; per-point mass).
