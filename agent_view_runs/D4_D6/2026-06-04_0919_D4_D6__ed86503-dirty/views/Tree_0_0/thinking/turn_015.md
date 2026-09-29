# Tree-0.0 · turn 15 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:32:20.880Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> x; rewrite supp_dexcepted supp_dinter /pred1 /=; smt(hf hfinv).`

---

Goal 1 is the support condition. On `D`'s support, `1<=x<=4`, and `finv x = a ⟺ x = f a` by the bijection hypotheses. Let me discharge with smt.
