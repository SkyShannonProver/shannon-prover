# Tree-0.0 · turn 24 · commit_tactic

<!-- session 3ad27182-af4d-4241-bfd6-16292deaeaf6 · 2026-06-04T16:35:20.572Z -->

**Intent:** `commit_tactic`  
**Payload:** `split=> h; smt(hf hfinv).`

---

`eq_iff` worked; smt fails on the full iff. Let me split into directions and let smt handle each.
