# Tree-0.0 · turn 48 · probe_tactic

<!-- session b8e9be0e-1cf4-4683-8c5a-2d6580fcbaef · 2026-06-10T22:06:06.442Z -->

**Intent:** `probe_tactic`  
**Payload:** `move=> c Hc Hdec; rewrite (take_nth witness) 1:/# mem_rcons in_cons.`

---

Let me read the source to understand `dec`, `mk_rs`, `topol`, and the surrounding lemmas.

I now understand the math. `dec gs k c <> None` iff `c.\`4 = genpoly1305 (get gs) k c.\`1 (topol c.\`2 c.\`3) = poly1305 r s (topol c.\`2 c.\`3)` with `(r,s)=mk_rs(oget gs.[(c.\`1,0)])`. In the new case `c.\`1=n0`, this is exactly the `test_poly` witness. Let me check for existing helper lemmas near `step2_2`.

No helper lemma exists — `step2_2` is the `admit.` I'm replacing. I'll build the manual proof. First probe the membership decomposition: `take (i+1) ns = rcons (take i ns) n0`, then split into `c.\`1 = n0` vs `c.\`1 \in take i ns`.
