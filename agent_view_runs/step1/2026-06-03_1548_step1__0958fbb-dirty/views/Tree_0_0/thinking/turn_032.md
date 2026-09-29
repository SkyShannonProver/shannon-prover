# Tree-0.0 · turn 32 · probe_tactic

<!-- session be8c2efe-b94f-4082-9c01-15b50a7a53eb · 2026-06-03T23:09:17.353Z -->

**Intent:** `probe_tactic`  
**Payload:** `proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq 1 1 : (t'{1} = t'{2} /\ t{1} = t{2} /\ n{1} = n{2} /\ a{1} = a{2} /\ c0{1} = c{2} /\ result{1} = result{2} /\ k{1} = IndBlock.k{2} /\ Mem.k{1} = IndBlock.k{2}). call poly_mac1. auto. smt(). if => //. wp. call chacha_enc1. auto. auto.`

---

Now I can see the post-`sp` structure. LHS locals: `k,n,a,c0,t,t',p0,result`; the matching (from pre) is LHS `(n,a,c0,t)` ↔ RHS `(n,a,c,t)`, `k{1}=Mem.k{1}=IndBlock.k{2}`. I'll cut after the `Poly.mac` with `seq 1 1` carrying the needed equalities, then handle the `if` with `chacha_enc1`. Probing the full dec proof.
