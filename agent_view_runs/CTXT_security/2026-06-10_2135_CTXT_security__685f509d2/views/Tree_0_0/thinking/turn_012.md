# Tree-0.0 · turn 12 · commit_tactic

<!-- session f8563eb0-33e2-483a-a365-92671a67224b · 2026-06-11T04:42:19.034Z -->

**Intent:** `commit_tactic`  
**Payload:** `by move=> _k _p; conseq (_: ={glob E, k, p} ==> ={glob E, res}) (E_corr _k _p) _ => //; proc true.`

---

Now prove the helper by combining the abstract self-equivalence with the `E_corr` hoare fact via three-judgment `conseq`.
