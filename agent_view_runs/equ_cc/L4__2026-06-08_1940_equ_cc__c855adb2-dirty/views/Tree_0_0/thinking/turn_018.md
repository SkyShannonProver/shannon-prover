# Tree-0.0 · turn 18 · commit_tactic

<!-- session 9380bb3d-763d-4a44-bfcc-de69cee4357c · 2026-06-09T02:52:08.816Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &m; auto; smt(C.ofintdK max_cipher_size_ok gt0_block_size size_ge0 size_eq0).`

---

Freshness side-goal: prove `x1 = (n0, ofintd i) ∉ ROF.m`. The invariant gives `(n0,c0) ∈ ROF.m => toint c0 < i`; instantiating at `c0 = ofintd i` with `toint(ofintd i) = i` yields a contradiction. Let me discharge with `auto; smt`.
