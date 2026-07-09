# Tree-0.1 · turn 1 · commit_tactic

<!-- session e9baec11-7b67-4080-97ec-c000f6e42fc2 · 2026-06-11T07:49:31.822Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> z; inline *; auto => />; smt(dpoly_in_ll).`

---

Resuming at the while-variant subgoal for the ns1 loop. The body contains an RO.get (a dpoly_in sample) plus deterministic assignments, so the standard close is intro the variant, inline the get, and discharge with auto + losslessness of dpoly_in.
