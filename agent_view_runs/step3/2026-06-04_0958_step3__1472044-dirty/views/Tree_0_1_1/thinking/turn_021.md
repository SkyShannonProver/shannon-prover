# Tree-0.1.1 · turn 21 · commit_tactic

<!-- session 04d4a898-436e-4cd4-8612-694f24113929 · 2026-06-04T17:45:15.790Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd (fun (s0:poly_out) => s0 + poly1305_eval r10{1} (topol a0{1} c3{1})) (fun (t0:poly_out) => t0 - poly1305_eval r10{1} (topol a0{1} c3{1})).`

---

Now `r6` is the last left sample, `t` the right one. Since `oget m_L.[x5] = r6` and `mk_rs (ofpair(ofpair(r10, r6), e)) = (r10, r6)`, the left tag is `t{1} = poly1305 r10 r6 (topol a0 c3) = r6 + poly1305_eval r10 (topol a0 c3)`. I couple `r6 ↦ t` by the offset bijection `s ↦ s + poly1305_eval r10 (topol a0 c3)` (inverse subtracts), which is measure-preserving on the funiform/full `dpoly_out`.
