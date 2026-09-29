# Tree-0.0 · turn 64 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:11:31.338Z -->

**Intent:** `probe_tactic`  
**Payload:** `move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=; rewrite Hgs /=; smt().`

---

The leaf needs `c` destructured so the `let (n0,a,c0,t)=c` reduces. Let me generalize the `c`-dependent hyps, unfold, destructure `c`, then close with `smt`.
