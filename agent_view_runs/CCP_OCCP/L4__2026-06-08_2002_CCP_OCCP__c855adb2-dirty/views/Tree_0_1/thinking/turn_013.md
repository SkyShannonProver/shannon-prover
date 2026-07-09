# Tree-0.1 · turn 13 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:08:15.784Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 0 : (c{1} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{1}) k{1} n{1} 1 p{1} /\ (n{2}, a{2}, p{2}) = nap{2} /\ c{2} = gen_CTR_encrypt_bytes take_xor (cc OCC.gs{2}) k{2} n{2} 1 p{2} /\ t{2} = genpoly1305 (cc OCC.gs{2}) k{2} n{2} (topol a{2} c{2}) /\ (n{1}, a{1}, p{1}) = nap{1} /\ k{1} = k{2} /\ nap{1} = nap{2} /\ OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}).`

---

Good, back to the post-`sp` state. Now I'll split the two LHS calls with `seq 1 0`, binding `c{1}` to the chacha output in the intermediate assertion so the `Poly.mac` step sees the correct `c`.
