# Tree-0.0 · turn 18 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:33:19.272Z -->

**Intent:** `commit_tactic`  
**Payload:** `rewrite /pred1 /=; smt(hf hfinv).`

---

Rewrites worked; earlier failure was the `/pred1 /=; smt` tail. Now unfold `pred1`, simplify, and close with smt.
