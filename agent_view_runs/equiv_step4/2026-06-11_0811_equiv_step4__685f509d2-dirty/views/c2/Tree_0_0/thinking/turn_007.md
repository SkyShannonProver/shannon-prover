# Tree-0.0 · turn 7 · commit_tactic

<!-- session 58bd62df-6813-481d-ba03-da6574d86ab1 · 2026-06-11T14:08:23.128Z -->

**Intent:** `commit_tactic`  
**Payload:** `move => &2 hneq hn1 hn2 hm1 hm2 r2L _ t3L _ r4L _ t4L _; split.`

---

`smt` choked on the combined goal (likely the lambda-heavy boolean part plus the fmap part together). I'll split the goal and handle each conjunct separately.
