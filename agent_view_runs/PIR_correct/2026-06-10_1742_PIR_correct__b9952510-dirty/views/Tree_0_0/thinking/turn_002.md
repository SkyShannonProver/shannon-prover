# Tree-0.0 · turn 2 · commit_tactic

<!-- session 4b15db9f-e792-4df5-8ff1-4c80d607c282 · 2026-06-11T00:44:08.202Z -->

**Intent:** `commit_tactic`  
**Payload:** `move=> hi0.`

---

Now I understand the goal. The result `res = r +^ r'` where `r`, `r'` are XOR-sums over `s`, `s'`, which differ exactly by `i0`. I'll prove this is almost-sure via `byphoare`. First intro the hypothesis.
