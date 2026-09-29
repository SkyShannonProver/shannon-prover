# Tree-0.0 · turn 40 · commit_tactic

<!-- session e8f72e76-a384-4fe6-8d81-b6f47e2ab598 · 2026-06-05T17:26:49.348Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> &2 _; proc; inline*.`

---

The enc-equiv goal is fully closed. Now the upto-bad losslessness side conditions. First: `CBC_Oracle(DoubleQuery(PRFi)).enc` is lossless. Strip the wrapper and inline.
