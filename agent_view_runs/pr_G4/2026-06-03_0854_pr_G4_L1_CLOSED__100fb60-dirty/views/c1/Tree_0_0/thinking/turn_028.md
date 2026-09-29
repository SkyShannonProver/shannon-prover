# Tree-0.0 · turn 28 · commit_tactic

<!-- session ba18a87c-18fd-43b1-83a4-965b4c3bbb9c · 2026-06-03T16:48:07.324Z -->

**Intent:** `commit_tactic`  
**Payload:** `apply mu_le => x _ /= [_ [hgx _]]; move: (map_f (logb G1.g_{hr}) (map (fun (t : PKE_.ciphertext) => t.`2) G3.cilog{hr}) (G1.g_{hr} ^ x) hgx); by rewrite (logbK G1.g_{hr} x hub).`

---

Goal 1: subset via `mu_le`, using `map_f` and `logbK` (log base `g_`).
