# Tree-0.0 · turn 12 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:37:40.075Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply mu_le => x _ /= [hx _]; by move: (map_f loge (map (fun (t : PKE_.ciphertext) => t.`1) G3.cilog{hr}) (g ^ x) hx); rewrite loggK.`

---

Goal 1 (sub-distribution monotonicity). Apply `mu_le` and use `map_f` + `loggK`.
