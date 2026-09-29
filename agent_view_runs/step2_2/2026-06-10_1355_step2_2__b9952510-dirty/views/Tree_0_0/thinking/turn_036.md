# Tree-0.0 · turn 36 · commit_tactic

<!-- session a8006092-a9db-4441-9330-0fc2cd05aaf8 · 2026-06-10T21:26:50.738Z -->

**Intent:** `commit_tactic`  
**Payload:** `suff h: test_poly c.`1 Mem.lc{hr} (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`1 (mk_rs (oget RO.m{hr}.[c.`1, C.ofintd 0])).`2 by smt(h).`

---

I'll read the latest workspace view to see the current proof state.

The goal is `forged{hr} || test_poly c.\`1 ...` and I have `hdec: dec RO.m{hr} Mem.k{hr} c <> None`. The `suff ... by rewrite h orbT` failed because `h: test_poly` is a bool, not an equation. Let me inspect the definitions of `dec` and `test_poly` to find the connection.

I now understand the math: `dec RO.m Mem.k c <> None` means `c.\`4 = poly1305 r0 s0 (topol c.\`2 c.\`3)` where `(r0,s0) = mk_rs (oget RO.m.[c.\`1, C.ofintd 0])`, and `test_poly` is satisfied with witness `c` (since `c \in Mem.lc` and `c.\`1 = c.\`1`). The previous closer failed because `rewrite h` can't rewrite a boolean fact here. Let me redo the reduction with `smt(h)` as the closer.
