# Tree-0.0 · turn 1 · commit_tactic

<!-- session 5a34e25e-6cb0-4b52-a73e-3dd4b84fb232 · 2026-06-06T12:46:44.374Z -->

**Intent:** `commit_tactic`  
**Payload:** `byequiv (_: ={glob D} ==> ={res}) => //.`

---

This is a substantial SHVZK equivalence proof. Let me understand the supporting definitions before committing to an approach.

I now understand the proof. Let me verify my mathematical plan with the advisor before committing to the interactive proof.

The math: 
- **gameIdeal**: `x=g^w`, `e` random, simulate gives `z0` random and `a=g^z0·x^(-e)=g^(z0-ew)`; verify always succeeds so `to=Some` and the `while(to=None)` loop runs 0 times. Trace `(a,e,z0)`.
- **gameReal**: `x=g^w`, `m=g^r` (r random), `e` random, `z=r+ew`. Trace `(m,e,z)`.
- **Coupling**: same `w`,`e`; couple ideal `z0` with real `r` via bijection `z0 = r+ew`. Then `z=z0`, `m=g^r=g^(z0-ew)=a`. Traces match → `D.distinguish` gives `={res}`.

Plan: `byequiv (_: ={glob D} ==> ={res})`, `proc`, inline, `rcondf{1}` to kill the loop (verify always true), `swap{2}` to reorder real's `r` sampling after `e`, `rnd` bijection, group algebra.

Excellent guidance. The dead-commit insight is key. Let me commit the skeleton first.
