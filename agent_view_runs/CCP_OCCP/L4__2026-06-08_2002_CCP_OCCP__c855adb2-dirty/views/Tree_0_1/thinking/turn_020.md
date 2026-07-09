# Tree-0.1 · turn 20 · commit_tactic

<!-- session bc388721-b6a3-44d0-b761-d8fe1f3df5c2 · 2026-06-09T03:10:55.393Z -->

**Intent:** `commit_tactic`  
**Payload:** `seq 1 1 : (t'{1} = t'{2} /\ result{1} = result{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c{1} = c{2} /\ t{1} = t{2} /\ k{1} = k{2} /\ OCC.gs{1} = OCC.gs{2} /\ (glob I){1} = (glob I){2}).`

---

Now `seq 1 1` to bridge `t'` (via `poly_spec`) and carry the equalities needed for the guard and branches.
