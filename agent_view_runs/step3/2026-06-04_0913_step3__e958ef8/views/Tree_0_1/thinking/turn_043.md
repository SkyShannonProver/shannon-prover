# Tree-0.1 · turn 43 · commit_tactic

<!-- session 214c307b-d923-4d2c-a74c-72e428a28c22 · 2026-06-04T16:41:33.713Z -->

**Intent:** `commit_tactic`  
**Payload:** `rnd (fun (u:poly_out) => u + poly1305_eval r5{1} (topol a0{1} c3{1})) (fun (u:poly_out) => u - poly1305_eval r5{1} (topol a0{1} c3{1})); wp; rnd{1}.`

---

The coupling works and `mk_rs_ofpair` will collapse the tag. Let me commit the coupling, absorb the rest, and discharge the `r5` sample.
