# Tree-0.1 · turn 2 · commit_tactic

<!-- session a19e92e2-12a7-4419-bd7f-3d37c1648b89 · 2026-06-12T01:02:19.107Z -->

**Intent:** `commit_tactic`  
**Payload:** `smt(size_ge0).`

---

Base case closed by `//=`. The inductive case follows from `ih` at `ci` plus arithmetic on `size c`; `smt` with the hypothesis in context should close it.
