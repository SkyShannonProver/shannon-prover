# Tree-0.1 · turn 9 · commit_tactic

<!-- session 32db57e0-fb2e-4cac-a35b-be9ba42eaabf · 2026-06-11T04:48:52.270Z -->

**Intent:** `commit_tactic`  
**Payload:** `by wp; call (_: true); call (_: true); skip; smt(in_fset0).`

---

All oracle obligations are closed — only the keygen initialization prefix remains. Both sides run `E.keygen` then `M.keygen`; coupling each with `call (_: true)` and discharging the fset0 residue.
