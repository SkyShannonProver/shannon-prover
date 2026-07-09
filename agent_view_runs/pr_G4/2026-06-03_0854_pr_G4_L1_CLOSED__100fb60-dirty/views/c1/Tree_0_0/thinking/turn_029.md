# Tree-0.0 · turn 29 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:48:26.120Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply (ler_trans (PKE_.qD%r * (1%r / (order - 1)%r))); last by smt(); apply (mu_mem_le_mu1_size (dt \ pred1 G1.u{hr}) (map (logb G1.g_{hr}) (map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog{hr})) (1%r / (order - 1)%r) PKE_.qD); [ by rewrite !size_map | by apply hmu1 ].`

---

Goal 2: bound by `qD·(1/(order-1))` then `mu_mem_le_mu1_size` with the two side conditions.
